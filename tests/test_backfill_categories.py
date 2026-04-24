'''Tests for the category backfill module.'''
import os
import sqlite3
import unittest

import pytest

from database.create_db import Database
from database.loader_LiveTrail import backfill_categories

pytestmark = pytest.mark.filterwarnings("ignore", message=".*XMLParsedAsHTMLWarning.*")


DB_PATH = 'test_backfill.db'


class TestHelpers(unittest.TestCase):
    def test_sex_category_from_sx(self):
        self.assertEqual(backfill_categories._sex_category_from_sx('F'), 'Female')
        self.assertEqual(backfill_categories._sex_category_from_sx('f'), 'Female')
        self.assertEqual(backfill_categories._sex_category_from_sx('H'), 'Male')
        self.assertEqual(backfill_categories._sex_category_from_sx('M'), 'Male')
        self.assertIsNone(backfill_categories._sex_category_from_sx(''))
        self.assertIsNone(backfill_categories._sex_category_from_sx('Z'))
        self.assertIsNone(backfill_categories._sex_category_from_sx(None))

    def test_full_category_from_identity_with_descat(self):
        self.assertEqual(
            backfill_categories._full_category_from_identity(
                {'descat': '0-34', 'sx': 'F', 'cat': ''}),
            '0-34 F',
        )
        self.assertEqual(
            backfill_categories._full_category_from_identity(
                {'descat': '35-39', 'sx': 'H', 'cat': ''}),
            '35-39 H',
        )

    def test_full_category_returns_none_when_descat_empty(self):
        # Chronic-empty events (seoul100k, 3monestirs, ...) expose sx but no
        # descat — there's no age bracket to publish so full_category must
        # stay NULL/empty for the caller to pass through COALESCE.
        self.assertIsNone(
            backfill_categories._full_category_from_identity(
                {'descat': '', 'sx': 'F', 'cat': ''})
        )
        self.assertIsNone(
            backfill_categories._full_category_from_identity(
                {'descat': '  ', 'sx': 'H', 'cat': ''})
        )

    def test_full_category_handles_unknown_sex(self):
        # descat present, sx blank: still publish the age bracket (sex suffix
        # stripped). Safer than inventing a sex we don't know.
        self.assertEqual(
            backfill_categories._full_category_from_identity(
                {'descat': '0-34', 'sx': '', 'cat': ''}),
            '0-34',
        )


class TestMigration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        Database.create_database(path=DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except PermissionError:
                pass  # Windows file-lock; harmless across test runs

    def test_create_database_includes_cat_needs_backfill(self):
        conn = sqlite3.connect(DB_PATH)
        try:
            cols = {row[1] for row in
                    conn.execute("PRAGMA table_info(races)").fetchall()}
        finally:
            conn.close()
        self.assertIn('cat_needs_backfill', cols)

    def test_ensure_cat_backfill_column_is_idempotent(self):
        # Running the migration on a DB that already has the column must not
        # raise or duplicate the column.
        Database.ensure_cat_backfill_column(DB_PATH)
        Database.ensure_cat_backfill_column(DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        try:
            cols = [row[1] for row in
                    conn.execute("PRAGMA table_info(races)").fetchall()]
        finally:
            conn.close()
        self.assertEqual(cols.count('cat_needs_backfill'), 1)


class TestDetector(unittest.TestCase):

    DETECTOR_DB = 'test_backfill_detector.db'

    @classmethod
    def setUpClass(cls):
        if os.path.exists(cls.DETECTOR_DB):
            os.remove(cls.DETECTOR_DB)
        Database.create_database(path=cls.DETECTOR_DB)
        conn = sqlite3.connect(cls.DETECTOR_DB)
        cur = conn.cursor()
        # Two events, three races, each seeded with different empty-cat rates.
        cur.executemany(
            "INSERT INTO events (event_id, code, name, year, country) "
            "VALUES (?, ?, ?, ?, ?)",
            [(1, 'utmb', 'UTMB', '2024', 'FR'),
             (2, 'penyagolosa', 'PENYAGOLOSA', '2026', 'ES')],
        )
        cur.executemany(
            "INSERT INTO races (race_id, event_id, race_name) VALUES (?, ?, ?)",
            [('utmb', 1, 'UTMB'),
             ('mim', 2, 'MIM'),
             ('csp', 2, 'CSP')],
        )
        # utmb: 10 rows, 1 empty (10%) — right at the threshold, should flag.
        # mim:  10 rows, 2 empty (20%) — above threshold, should flag.
        # csp:  10 rows, 0 empty (0%) — below threshold, should not flag.
        rows = []
        for i in range(10):
            rows.append((
                'utmb', 1, i + 1, f'{i}', 'U', 'U',
                '' if i == 0 else '35-39 F',
                'UTMB', '10:00:00',
            ))
            rows.append((
                'mim', 2, i + 1, f'{i}', 'P', 'P',
                '' if i < 2 else '35-39 F',
                'MIM', '10:00:00',
            ))
            rows.append((
                'csp', 2, i + 1, f'{i}', 'C', 'C', '35-39 F',
                'CSP', '10:00:00',
            ))
        cur.executemany(
            "INSERT INTO results "
            "(race_id, event_id, position, bib, surname, name, full_category, "
            "sex_category, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.DETECTOR_DB):
            try:
                os.remove(cls.DETECTOR_DB)
            except PermissionError:
                pass

    def test_detect_flags_races_above_threshold(self):
        flagged = backfill_categories.detect_races_needing_backfill(
            self.DETECTOR_DB, threshold=0.10,
        )
        keys = {(eid, rid) for eid, rid, _ in flagged}
        # UTMB sits at exactly 10% and should flag; MIM is at 20% and should
        # flag; CSP is at 0% and must not flag.
        self.assertIn((1, 'utmb'), keys)
        self.assertIn((2, 'mim'), keys)
        self.assertNotIn((2, 'csp'), keys)

    def test_detect_is_idempotent(self):
        # Re-running the detector returns an empty list because the flag is
        # already set — the caller uses the returned deltas for logging.
        backfill_categories.detect_races_needing_backfill(
            self.DETECTOR_DB, threshold=0.10,
        )
        second = backfill_categories.detect_races_needing_backfill(
            self.DETECTOR_DB, threshold=0.10,
        )
        self.assertEqual(second, [])

    def test_list_flagged_races_filters_by_event_id(self):
        backfill_categories.detect_races_needing_backfill(
            self.DETECTOR_DB, threshold=0.10,
        )
        flagged_event_2 = backfill_categories.list_flagged_races(
            self.DETECTOR_DB, event_ids=[2],
        )
        race_ids = {row[1] for row in flagged_event_2}
        self.assertEqual(race_ids, {'mim'})


if __name__ == '__main__':
    unittest.main()
