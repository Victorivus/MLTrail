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
        # Remove the test.db file if it exists
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_create_database(self):
        # Ensure that the database is created successfully
        self.assertFalse(os.path.exists(self.db_path))
        Database.create_database(self.db_path)
        self.assertTrue(os.path.exists(self.db_path))

        # Check if the necessary tables are created
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        self.assertIn('events', table_names)
        self.assertIn('races', table_names)
        self.assertIn('results', table_names)
        self.assertIn('control_points', table_names)
        self.assertIn('timing_points', table_names)
        self.assertIn('features', table_names)
        conn.close()

    def test_empty_all_tables(self):
        # Create a database and populate it with some data
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
        unused_functions = get_untested_functions(Database, TestDatabase)
        print(unused_functions)
        assert len(unused_functions) == 0, "Database is not tested enough. pytest -s for details."


if __name__ == '__main__':
    unittest.main()
