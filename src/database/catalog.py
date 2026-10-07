'''
    Read-only summaries of what the local results database holds.

    The pages use these instead of hard-coded text or LiveTrail-only lists:
    LiveTrail's archived-years feed lags behind the current season (in October
    2026 it listed 18 events with a 2026 edition while the DB had results for
    117), so the DB is the better source for "which editions exist".
'''
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DataFreshness:
    '''How much data the DB holds and the most recent race with results.'''
    n_editions: int
    n_races: int
    latest_start: Optional[datetime]

    def caption(self) -> str:
        '''One-line description for the UI, e.g. "… up to 27/09/2026."'''
        if self.latest_start is None:
            return "Results scraped from LiveTrail (no race results loaded yet)."
        return (f"Results scraped from LiveTrail: {self.n_editions:,} event editions, "
                f"{self.n_races:,} races, up to {self.latest_start:%d/%m/%Y}.")


def _connect_ro(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def event_years_with_results(db_path: str) -> dict:
    '''``{event_code: [year, ...]}`` (newest first) for editions with results.'''
    conn = _connect_ro(db_path)
    try:
        # Probe results per race through its (race_id, event_id, bib) primary
        # key. Filtering events by event_id alone has no index and makes
        # SQLite scan all results (~1 s locally, ~40 s over Docker's mount).
        rows = conn.execute(
            "SELECT DISTINCT e.code, e.year FROM races r "
            "JOIN events e ON e.event_id = r.event_id "
            "WHERE EXISTS (SELECT 1 FROM results x "
            "              WHERE x.race_id = r.race_id AND x.event_id = r.event_id)"
        ).fetchall()
    finally:
        conn.close()
    years = {}
    for code, year in rows:
        years.setdefault(code, []).append(str(year))
    for code in years:
        years[code].sort(reverse=True)
    return years


def merge_years(*sources: dict) -> dict:
    '''Union of several ``{event: [years]}`` maps, years sorted newest first.'''
    merged = {}
    for source in sources:
        for event, years in source.items():
            merged.setdefault(event, set()).update(str(y) for y in years)
    return {event: sorted(years, reverse=True) for event, years in merged.items()}


def data_freshness(db_path: str) -> DataFreshness:
    '''Counts of event editions and races, and the latest race with results.'''
    conn = _connect_ro(db_path)
    try:
        n_editions, n_races = conn.execute(
            "SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM races)"
        ).fetchone()
        latest = conn.execute(
            "SELECT r.departure_datetime FROM races r "
            "WHERE r.departure_datetime IS NOT NULL AND EXISTS ("
            "  SELECT 1 FROM results x WHERE x.event_id = r.event_id "
            "  AND x.race_id = r.race_id) "
            "ORDER BY r.departure_datetime DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    latest_start = None
    if latest is not None:
        try:
            latest_start = datetime.fromisoformat(latest[0])
        except (TypeError, ValueError):
            latest_start = None
    return DataFreshness(n_editions, n_races, latest_start)
