'''
    Test module for Database
'''
import unittest
import os
import sqlite3
from database.create_db import Database
from tests.tools import get_untested_functions


class TestDatabase(unittest.TestCase):
    '''
        Test class for Database
    '''
    db_path = 'test.db'
    if os.path.exists(db_path):
        os.remove(db_path)

    def setUp(self):
        self.db_path = 'test.db'

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    @classmethod
    def tearDownClass(self):
        '''
            Remove the test.db file if it exists
        '''
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_database(self):
        '''
            Ensure that the database is created successfully
        '''
        self.assertFalse(os.path.exists(self.db_path))
        Database.create_database(self.db_path)
        self.assertTrue(os.path.exists(self.db_path))

        # Check if the necessary tables are created
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        self.assertIn('users', table_names)
        self.assertIn('events', table_names)
        self.assertIn('races', table_names)
        self.assertIn('results', table_names)
        self.assertIn('control_points', table_names)
        self.assertIn('timing_points', table_names)
        self.assertIn('features', table_names)
        self.assertIn('models', table_names)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        index_names = {row[0] for row in cursor.fetchall()}
        self.assertTrue({'features_event_race_bib', 'results_surname_lower',
                         'models_one_active'} <= index_names)
        conn.close()

    def test_create_models_table(self):
        '''
            The models table allows several versions but one active model per user
        '''
        conn = sqlite3.connect(self.db_path)
        Database.create_models_table(conn)
        Database.create_models_table(conn)  # idempotent
        row = ("algo", 1, "[]", b"x", "sha", "skops")
        insert = ("INSERT INTO models (user_id, is_active, algorithm, feature_schema_version, "
                  "training_set, artifact, artifact_sha256, artifact_format) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
        conn.execute(insert, (1, 1) + row)
        conn.execute(insert, (1, 0) + row)
        conn.execute(insert, (2, 1) + row)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(insert, (1, 1) + row)
        conn.close()

    def test_ensure_indexes(self):
        '''
            Missing app indexes are created once; later runs are no-ops
        '''
        Database.create_database(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP INDEX features_event_race_bib")
        conn.execute("DROP INDEX results_surname_lower")
        conn.commit()
        conn.close()

        created = Database.ensure_indexes(self.db_path)
        self.assertEqual(sorted(created), ['features_event_race_bib', 'results_surname_lower'])
        self.assertEqual(Database.ensure_indexes(self.db_path), [])

        conn = sqlite3.connect(self.db_path)
        plan = " ".join(r[3] for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM features "
            "WHERE event_id = 1 AND race_id = 'r' AND bib = '1'"))
        conn.close()
        self.assertIn('features_event_race_bib', plan)

    def test_migrate_existing_database(self):
        '''
            database.migrate upgrades a DB that predates models and indexes
        '''
        from database.migrate import migrate
        Database.create_database(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.execute("DROP TABLE models")
        conn.execute("DROP INDEX features_event_race_bib")
        conn.commit()
        conn.close()

        self.assertEqual(migrate(self.db_path), ['features_event_race_bib'])
        self.assertEqual(migrate(self.db_path), [])
        conn = sqlite3.connect(self.db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.assertIn('models', tables)

    def test_empty_all_tables(self):
        '''
            Create a database and populate it with some data
        '''
        Database.create_database(self.db_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO events (code, name, year, country) VALUES ('event1', 'Event One', '2022', 'Country1');")
        cursor.execute("INSERT INTO races (race_id, event_id, race_name) VALUES ('race1', 1, 'Race One');")
        conn.commit()
        conn.close()

        # Ensure that tables are not empty before calling empty_all_tables
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events;")
        rows = cursor.fetchall()
        self.assertTrue(len(rows) > 0)
        cursor.execute("SELECT * FROM races;")
        rows = cursor.fetchall()
        self.assertTrue(len(rows) > 0)
        conn.close()

        # Call empty_all_tables
        Database.empty_all_tables(self.db_path)

        # Ensure that tables are empty after calling empty_all_tables
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events;")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 0)
        cursor.execute("SELECT * FROM races;")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 0)
        conn.close()

    def test_implemented_tests(self):
        '''
            Check that all functions are tested
        '''
        unused_functions = get_untested_functions(Database, TestDatabase)
        print(unused_functions)
        assert len(unused_functions) == 0, "Database is not tested enough. pytest -s for details."


if __name__ == '__main__':
    unittest.main()
