"""One-shot resume for `database.loader_LiveTrail.backfill_categories`.

The original backfill run against events.db:
  * processed ~25 flagged races fully,
  * hit 3/3 retry failures on a handful of individual bibs (DNS drops during
    a LiveTrail window),
  * ended up crashing on ``sqlite3.OperationalError: database is locked``
    midway through the list,

so a good chunk of flagged races were never visited at all and a small
fraction of bibs inside completed races still have empty categories.

This script is a **one-shot** recovery run. It:

  1. Parses the existing ``backfill.log`` (or whatever file you point it at
     via ``--log``) to see which races finished, and which bibs failed 3/3
     so we can note them in the resume log.
  2. Queries the DB for the **actual** remaining work per flagged race —
     ``sex_category IS NULL`` is the truthy "this bib never got a coureur.php
     hit" signal, because even chronic-empty events (where descat is blank)
     get ``sex_category`` populated on a successful backfill while
     ``full_category`` stays empty.
  3. Iterates flagged races in order, skipping those with zero remaining
     bibs, and calling ``get_runner_identity`` for the ones still missing.

The script is idempotent: running it again after another interruption will
pick up exactly where it left off. It writes its own progress log to
``backfill_resume.log`` so the original log is not clobbered.

Usage::

    PYTHONPATH=src python scripts/resume_backfill.py \\
        --path data/events.db \\
        --log backfill.log

Options are the same as the main backfill CLI plus ``--log`` and ``--dry-run``.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database.loader_LiveTrail.backfill_categories import (  # noqa: E402
    DEFAULT_EMPTY_CAT_THRESHOLD,
    _full_category_from_identity,
    _recompute_cat_rankings_for_race,
    _sex_category_from_sx,
    list_flagged_races,
)
from database.create_db import Database  # noqa: E402
from scraper.scraper import LiveTrailScraper  # noqa: E402

logger = logging.getLogger(__name__)

# Parses a "Backfilled penyagolosa 2025 mim: attempted=273 updated=273" line.
BACKFILL_RE = re.compile(
    r"Backfilled\s+(\S+)\s+(\S+)\s+(\S+):\s+attempted=(\d+)\s+updated=(\d+)"
)
# Parses "Request failed after 3 retries: https://livetrail.net/histo/<ev>_<yr>/coureur.php?rech=<bib>"
# Two URL shapes exist: "<event>_<year>" and "<event><year>".
FAILED_RE = re.compile(
    r"Request failed after 3 retries:\s+"
    r"https://livetrail\.net/histo/(?P<slug>[A-Za-z0-9]+?)_?(?P<year>\d{4})/"
    r"coureur\.php\?rech=(?P<bib>\S+)"
)


def parse_backfill_log(log_path: str) -> tuple[set[tuple[str, str, str]],
                                                dict[tuple[str, str], set[str]]]:
    """Return ``(completed_races, failed_bibs)`` from a prior run's log.

    ``completed_races`` is a set of ``(event_code, year, race_id)`` triples
    seen in "Backfilled ... attempted=N updated=M" lines — regardless of
    whether N == M, because the DB-level "still has empty category" check
    below tells us exactly which bibs are genuinely still open.

    ``failed_bibs`` is keyed by ``(event_code, year)`` and collects the bibs
    LiveTrail refused after 3 retries. We surface these in the resume log
    so the user can see what was physically unreachable versus what was
    just not attempted yet.
    """
    completed: set[tuple[str, str, str]] = set()
    failed: dict[tuple[str, str], set[str]] = defaultdict(set)

    if not os.path.exists(log_path):
        logger.warning("Log %s not found — nothing to parse.", log_path)
        return completed, failed

    with open(log_path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            m = BACKFILL_RE.search(line)
            if m:
                completed.add((m.group(1), m.group(2), m.group(3)))
                continue
            m = FAILED_RE.search(line)
            if m:
                key = (m.group("slug"), m.group("year"))
                failed[key].add(m.group("bib"))

    return completed, failed


def fetch_pending_bibs(db_path: str, event_id: int, race_id: str) -> list[str]:
    """Bibs that still need a coureur.php hit.

    ``sex_category IS NULL`` is the authoritative signal: the first
    successful call to ``get_runner_identity`` on a bib always writes a
    sex_category value (H→Male, F→Female). If it's still NULL, the bib
    was either never attempted or failed all retries. ``full_category``
    can legitimately remain empty on chronic-empty events, so filtering
    only on it would re-hit every already-processed row on those events.
    """
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT bib FROM results
            WHERE event_id = ? AND race_id = ?
              AND sex_category IS NULL
              AND (full_category IS NULL OR full_category = '')
            """,
            (event_id, race_id),
        )
        return [row[0] for row in cursor.fetchall() if row[0]]
    finally:
        conn.close()


def apply_identity(db_path: str, event_id: int, race_id: str,
                   bib: str, identity: dict) -> bool:
    """Write the derived sex / full category to the results row.

    Returns True when the row was updated with at least one of the two
    columns. COALESCE protects existing values from being clobbered by
    nulls in the identity payload.
    """
    sex_cat = _sex_category_from_sx(identity.get("sx", ""))
    full_cat = _full_category_from_identity(identity)
    if sex_cat is None and full_cat is None:
        return False
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE results
            SET sex_category = COALESCE(?, sex_category),
                full_category = COALESCE(NULLIF(?, ''), full_category)
            WHERE event_id = ? AND race_id = ? AND bib = ?
            """,
            (sex_cat, full_cat, event_id, race_id, bib),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def resume_race(scraper: LiveTrailScraper, db_path: str,
                event_id: int, race_id: str, event_code: str, year: str,
                pending_bibs: list[str]) -> tuple[int, int]:
    """Retry the given bibs for one race. Returns ``(attempted, updated)``."""
    attempted = 0
    updated = 0
    for bib in pending_bibs:
        if not bib:
            continue
        attempted += 1
        identity = scraper.get_runner_identity(event_code, year, bib)
        if identity is None:
            continue
        if apply_identity(db_path, event_id, race_id, bib, identity):
            updated += 1
    if updated:
        _recompute_cat_rankings_for_race(db_path, event_id, race_id)
    return attempted, updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume a previous backfill_categories run where it left off."
    )
    parser.add_argument("-p", "--path", required=True, help="DB path.")
    parser.add_argument("-l", "--log", default="backfill.log",
                        help="Path to the prior run's log file.")
    parser.add_argument("-t", "--threshold", type=float,
                        default=DEFAULT_EMPTY_CAT_THRESHOLD,
                        help="Empty-cat ratio for the detector "
                             f"(default {DEFAULT_EMPTY_CAT_THRESHOLD}).")
    parser.add_argument("--event-id", type=int, action="append",
                        help="Restrict to one or more event_ids (may be repeated).")
    parser.add_argument("--skip", action="append", default=[],
                        help="Skip a race spelled 'event_code[:year[:race_id]]'. "
                             "May be repeated. Examples: '--skip marxainfantil' "
                             "skips every marxainfantil year/race; "
                             "'--skip marxainfantil:2025' skips all marxainfantil "
                             "2025 races; '--skip marxainfantil:2025:marxa' skips "
                             "just that one race.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan without issuing any HTTP calls.")
    args = parser.parse_args()

    # Parse --skip into a list of (code, year_or_None, race_or_None) tuples.
    skip_rules: list[tuple[str, str | None, str | None]] = []
    for raw in args.skip:
        parts = raw.split(":")
        if len(parts) == 1:
            skip_rules.append((parts[0], None, None))
        elif len(parts) == 2:
            skip_rules.append((parts[0], parts[1], None))
        elif len(parts) == 3:
            skip_rules.append((parts[0], parts[1], parts[2]))
        else:
            parser.error(f"--skip takes at most 3 colon-separated fields: {raw!r}")

    def is_skipped(code: str, year: str, race_id: str) -> bool:
        for c, y, r in skip_rules:
            if c != code:
                continue
            if y is not None and y != year:
                continue
            if r is not None and r != race_id:
                continue
            return True
        return False

    # Keep the resume output separate from the original backfill.log so
    # you can diff timelines if needed.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("backfill_resume.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    db_path = os.path.abspath(args.path)
    logger.info("Resuming against %s (log: %s)", db_path, args.log)

    # Ensure migration has been applied (idempotent).
    Database.ensure_cat_backfill_column(db_path)

    completed, failed_bibs = parse_backfill_log(args.log)
    logger.info("Log summary: %d races reported completed, "
                "%d (event,year) pairs with failed bibs (total %d failed bibs).",
                len(completed), len(failed_bibs),
                sum(len(b) for b in failed_bibs.values()))

    flagged = list_flagged_races(db_path, event_ids=args.event_id)
    logger.info("Flagged races in DB: %d", len(flagged))

    # Build the work plan: for every flagged race, query the DB for the
    # actual pending bibs. This is what matters — the log only hints at
    # what happened, the DB is the source of truth for what's still open.
    plan: list[tuple[int, str, str, str, list[str]]] = []
    skipped_count = 0
    for event_id, race_id, event_code, year in flagged:
        if is_skipped(event_code, year, race_id):
            skipped_count += 1
            logger.info("Skipping %s %s %s (matched --skip rule)",
                        event_code, year, race_id)
            continue
        pending = fetch_pending_bibs(db_path, event_id, race_id)
        if pending:
            plan.append((event_id, race_id, event_code, year, pending))

    total_pending = sum(len(p[4]) for p in plan)
    logger.info("Resume plan: %d race(s) with pending bibs, %d bibs total.",
                len(plan), total_pending)

    if args.dry_run:
        for event_id, race_id, event_code, year, pending in plan[:50]:
            fail_key = (event_code, year)
            prior_failed = len(failed_bibs.get(fail_key, set()))
            already_completed = (event_code, year, race_id) in completed
            logger.info(
                "  [%s %s %s] pending=%d prior_failed_in_log=%d already_logged_done=%s",
                event_code, year, race_id, len(pending), prior_failed,
                already_completed,
            )
        if len(plan) > 50:
            logger.info("  ... and %d more races", len(plan) - 50)
        logger.info("Dry run — no HTTP calls made.")
        return

    scraper = LiveTrailScraper()
    total_updated = 0
    for event_id, race_id, event_code, year, pending in plan:
        logger.info("Resuming %s %s %s (%d pending bibs)...",
                    event_code, year, race_id, len(pending))
        attempted, updated = resume_race(
            scraper, db_path, event_id, race_id, event_code, year, pending,
        )
        total_updated += updated
        # Match the "Backfilled ... attempted=N updated=M" format emitted by
        # database.loader_LiveTrail.backfill_categories so this resume log
        # is itself re-parseable by another pass of this script if the
        # resume run also gets interrupted.
        logger.info("Backfilled %s %s %s: attempted=%d updated=%d",
                    event_code, year, race_id, attempted, updated)

    logger.info("Resume finished: %d row(s) updated across %d race(s).",
                total_updated, len(plan))


if __name__ == "__main__":
    main()
