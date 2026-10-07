'''
Tests for database.catalog: DB-derived event years and data freshness.
'''
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime

from database.catalog import (event_years_with_results, merge_years,
                              data_freshness)
from database.create_db import Database


class CatalogTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self._tmp.name, "events.db")
        Database.create_database(self.db)
        conn = sqlite3.connect(self.db)
        conn.executemany(
            "INSERT INTO events (event_id, code, name, year) VALUES (?, ?, ?, ?)",
            [(1, "penyagolosa", "PENYAGOLOSA TRAILS", "2025"),
             (2, "penyagolosa", "PENYAGOLOSA TRAILS", "2026"),
             (3, "tar", "TRAIL DES AIGUILLES ROUGES", "2026"),
             (4, "future", "NOT RACED YET", "2027")])
        conn.executemany(
            "INSERT INTO races (race_id, event_id, race_name, departure_datetime) "
            "VALUES (?, ?, ?, ?)",
            [("csp", 1, "CSP", "2025-04-12 00:00:02"),
             ("csp", 2, "CSP", "2026-04-18 00:00:01"),
             ("tar", 3, "TAR", "2026-09-27 05:00:02"),
             ("x", 4, "X", "2027-01-01 08:00:00")])  # no results yet
        conn.executemany(
            "INSERT INTO results (race_id, event_id, bib, time) VALUES (?, ?, ?, ?)",
            [("csp", 1, "1", "20:00:00"), ("csp", 2, "1", "19:00:00"),
             ("tar", 3, "7", "10:00:00")])
        conn.commit()
        conn.close()

    def tearDown(self):
        self._tmp.cleanup()


class TestEventYears(CatalogTestCase):
    def test_only_editions_with_results(self):
        self.assertEqual(event_years_with_results(self.db),
                         {"penyagolosa": ["2026", "2025"], "tar": ["2026"]})

    def test_merge_adds_db_years_missing_from_livetrail_feed(self):
        feed = {"penyagolosa": ["2025", "2024"], "utmb": ["2025"]}
        merged = merge_years(feed, event_years_with_results(self.db))
        self.assertEqual(merged["penyagolosa"], ["2026", "2025", "2024"])
        self.assertEqual(merged["utmb"], ["2025"])
        self.assertEqual(merged["tar"], ["2026"])
        self.assertEqual(feed["penyagolosa"], ["2025", "2024"])  # inputs untouched


class TestDataFreshness(CatalogTestCase):
    def test_latest_race_with_results(self):
        f = data_freshness(self.db)
        self.assertEqual((f.n_editions, f.n_races), (4, 4))
        self.assertEqual(f.latest_start, datetime(2026, 9, 27, 5, 0, 2))
        self.assertEqual(f.caption(),
                         "Results scraped from LiveTrail: 4 event editions, 4 races, "
                         "up to 27/09/2026.")

    def test_empty_database(self):
        empty = os.path.join(self._tmp.name, "empty.db")
        Database.create_database(empty)
        f = data_freshness(empty)
        self.assertIsNone(f.latest_start)
        self.assertIn("no race results loaded yet", f.caption())

    def test_reads_do_not_write(self):
        before = os.path.getmtime(self.db)
        event_years_with_results(self.db)
        data_freshness(self.db)
        self.assertEqual(os.path.getmtime(self.db), before)


if __name__ == "__main__":
    unittest.main()
