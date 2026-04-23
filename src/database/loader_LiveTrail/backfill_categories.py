"""Backfill missing category data for races where LiveTrail's bulk XML omits it.

Some organizers stopped serialising the ``cat`` attribute in ``passages.php``
for a subset of runners (the Spanish cluster — Penyagolosa, Olla de Núria,
Epic Trail Costa Daurada — dropped the SE/<35 bracket starting 2025; a longer
tail of events, mostly Asian ultras and mass-participation races, never
published categories at all). The per-runner ``coureur.php`` endpoint still
exposes ``sx`` (H/F) and sometimes ``descat`` (the age bracket), so we can
recover at least the sex, and when ``descat`` is present a full category
label as well.

Detection: for every race in the DB, count rows with NULL/empty
``full_category``. If the ratio crosses a threshold we set
``races.cat_needs_backfill = 1``; the flag persists so future loader runs
know to re-apply the backfill when they see new data for that race.

Backfill: for every flagged race, fetch ``coureur.php`` per empty-cat bib,
update ``results.sex_category`` directly (H → Male, F → Female) and
``results.full_category`` when ``descat`` is available, then recompute
category rankings for the race.
"""
import argparse
import logging
import os
import sqlite3
from typing import Iterable

from config import get_config
from database.create_db import Database
from scraper.scraper import LiveTrailScraper

logger = logging.getLogger(__name__)

# Ratio of empty-cat rows above which a race is considered "needs backfill".
# Asian/mass-participation events that never publish categories sit at or near
# 100%; the Spanish 2025+ cluster hovers in the 15-30% range. 10% is low enough
# to catch both without snagging UTMB-style races whose baseline is <0.5%.
DEFAULT_EMPTY_CAT_THRESHOLD = 0.10

_SEX_MAP = {'F': 'Female', 'H': 'Male', 'M': 'Male'}


def _sex_category_from_sx(sx: str) -> str | None:
    return _SEX_MAP.get((sx or '').upper())


def _full_category_from_identity(identity: dict) -> str | None:
    """Rebuild a ``full_category`` string from ``descat`` + ``sx``.

    Returns ``None`` when ``descat`` is empty — the caller should leave
    ``full_category`` alone in that case, since we have no age bracket to
    publish even if we know the runner's sex.
    """
    descat = (identity.get('descat') or '').strip()
    sx = (identity.get('sx') or '').strip().upper()
    if not descat:
        return None
    suffix = 'F' if sx == 'F' else 'H' if sx in ('H', 'M') else ''
    # "0-34 F" rather than "0-34F" keeps it visually close to the existing
    # "- F" / "MA30H" shapes the DB has for older penyagolosa rows.
    return f"{descat} {suffix}".strip()


def _open(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, timeout=30)


def detect_races_needing_backfill(
    db_path: str,
    threshold: float = DEFAULT_EMPTY_CAT_THRESHOLD,
) -> list[tuple[int, str, float]]:
    """Scan every race and flag those exceeding the empty-cat ratio.

    Returns the list of ``(event_id, race_id, ratio)`` tuples that were
    newly flagged this run (rows that were already flagged are not returned
    again, so the caller can log only the deltas).
    """
    Database.ensure_cat_backfill_column(db_path)
    conn = _open(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.event_id, r.race_id, r.cat_needs_backfill,
                   COUNT(*) AS total,
                   SUM(CASE WHEN res.full_category IS NULL
                                 OR res.full_category = ''
                            THEN 1 ELSE 0 END) AS empty_cat
            FROM races r
            INNER JOIN results res
                ON res.event_id = r.event_id AND res.race_id = r.race_id
            GROUP BY r.event_id, r.race_id
        ''')
        newly_flagged = []
        for event_id, race_id, already_flagged, total, empty in cursor.fetchall():
            if total == 0:
                continue
            ratio = empty / total
            if ratio >= threshold and not already_flagged:
                cursor.execute(
                    "UPDATE races SET cat_needs_backfill = 1 "
                    "WHERE event_id = ? AND race_id = ?",
                    (event_id, race_id),
                )
                newly_flagged.append((event_id, race_id, ratio))
        conn.commit()
        return newly_flagged
    finally:
        conn.close()


def list_flagged_races(
    db_path: str,
    event_ids: Iterable[int] | None = None,
) -> list[tuple[int, str, str, str]]:
    """Return ``(event_id, race_id, event_code, year)`` for flagged races.

    Optionally restrict to a subset of ``event_ids`` so loaders can process
    only what they just touched during an ``--update`` run.
    """
    conn = _open(db_path)
    try:
        cursor = conn.cursor()
        params: list = []
        query = '''
            SELECT r.event_id, r.race_id, e.code, e.year
            FROM races r
            INNER JOIN events e ON e.event_id = r.event_id
            WHERE r.cat_needs_backfill = 1
        '''
        if event_ids is not None:
            ids = list(event_ids)
            if not ids:
                return []
            query += f" AND r.event_id IN ({','.join('?' * len(ids))})"
            params.extend(ids)
        query += ' ORDER BY e.year DESC, e.code, r.race_id'
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


def backfill_race(
    scraper: LiveTrailScraper,
    db_path: str,
    event_id: int,
    race_id: str,
    event_code: str,
    year: str,
) -> tuple[int, int]:
    """Fetch per-runner identity for every empty-cat bib in the race.

    Returns ``(attempted, updated)`` so the caller can log progress.
    """
    conn = _open(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT bib FROM results
            WHERE event_id = ? AND race_id = ?
              AND (full_category IS NULL OR full_category = '')
            ''',
            (event_id, race_id),
        )
        bibs = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    attempted = 0
    updated = 0
    for bib in bibs:
        if not bib:
            continue
        attempted += 1
        identity = scraper.get_runner_identity(event_code, year, bib)
        if identity is None:
            continue
        sex_cat = _sex_category_from_sx(identity.get('sx', ''))
        full_cat = _full_category_from_identity(identity)
        if sex_cat is None and full_cat is None:
            continue
        conn = _open(db_path)
        try:
            cursor = conn.cursor()
            # COALESCE keeps any non-null existing value we may not want to
            # overwrite if the result row has been partially populated.
            cursor.execute(
                '''
                UPDATE results
                SET sex_category = COALESCE(?, sex_category),
                    full_category = COALESCE(NULLIF(?, ''), full_category)
                WHERE event_id = ? AND race_id = ? AND bib = ?
                ''',
                (sex_cat, full_cat, event_id, race_id, bib),
            )
            conn.commit()
        finally:
            conn.close()
        updated += 1

    if updated:
        _recompute_cat_rankings_for_race(db_path, event_id, race_id)
    logger.info(
        "Backfilled %s %s %s: attempted=%d updated=%d",
        event_code, year, race_id, attempted, updated,
    )
    return attempted, updated


def _recompute_cat_rankings_for_race(db_path: str, event_id: int, race_id: str) -> None:
    """Recompute cat_position / full_cat_position for a single race.

    Mirrors ``CSV_to_DB_results.compute_category_rankings`` but scoped to one
    race so we don't re-rank the whole event every time we backfill a race.
    """
    conn = _open(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            WITH RankedResults AS (
                SELECT race_id, event_id, bib,
                       RANK() OVER (PARTITION BY race_id, event_id, sex_category
                                    ORDER BY time) AS cat_rank,
                       RANK() OVER (PARTITION BY race_id, event_id, full_category
                                    ORDER BY time) AS full_cat_rank
                FROM results
                WHERE full_category NOT LIKE '' AND full_category IS NOT NULL
                  AND time NOT LIKE '' AND time IS NOT NULL
                  AND event_id = ? AND race_id = ?
            )
            UPDATE results
            SET cat_position = RankedResults.cat_rank,
                full_cat_position = RankedResults.full_cat_rank
            FROM RankedResults
            WHERE results.race_id = RankedResults.race_id
              AND results.event_id = RankedResults.event_id
              AND results.bib = RankedResults.bib
              AND results.event_id = ?
              AND results.race_id = ?
            ''',
            (event_id, race_id, event_id, race_id),
        )
        conn.commit()
    finally:
        conn.close()


def backfill_all(
    db_path: str,
    event_ids: Iterable[int] | None = None,
    threshold: float = DEFAULT_EMPTY_CAT_THRESHOLD,
) -> None:
    """Detect + backfill every flagged race.

    Call with ``event_ids`` to restrict the run (used by the loader to touch
    only what it just updated). Call with no filter for the one-shot.
    """
    Database.ensure_cat_backfill_column(db_path)
    newly = detect_races_needing_backfill(db_path, threshold=threshold)
    for event_id, race_id, ratio in newly:
        logger.info(
            "Flagged for backfill: event_id=%s race_id=%s empty_ratio=%.1f%%",
            event_id, race_id, ratio * 100,
        )

    flagged = list_flagged_races(db_path, event_ids=event_ids)
    if not flagged:
        logger.info("No flagged races to backfill.")
        return

    scraper = LiveTrailScraper()
    total_updated = 0
    for event_id, race_id, event_code, year in flagged:
        _, updated = backfill_race(
            scraper, db_path, event_id, race_id, event_code, year,
        )
        total_updated += updated
    logger.info("Backfill finished: %d row(s) updated across %d race(s)",
                total_updated, len(flagged))


def main() -> None:
    '''Entry point for the one-shot CLI.'''
    cfg = get_config()
    parser = argparse.ArgumentParser(
        description='Backfill sex/category data for races where '
                    "LiveTrail's bulk XML is incomplete.",
    )
    parser.add_argument('-p', '--path', default=cfg.db_path, help='DB path.')
    parser.add_argument(
        '-t', '--threshold', type=float, default=DEFAULT_EMPTY_CAT_THRESHOLD,
        help=f'Empty-cat ratio that flags a race '
             f'(default {DEFAULT_EMPTY_CAT_THRESHOLD}).',
    )
    parser.add_argument(
        '--event-id', type=int, action='append',
        help='Restrict to one or more event_ids (may be repeated).',
    )
    args = parser.parse_args()
    backfill_all(
        db_path=os.path.abspath(args.path),
        event_ids=args.event_id,
        threshold=args.threshold,
    )


if __name__ == '__main__':
    main()
