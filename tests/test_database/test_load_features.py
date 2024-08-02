import unittest
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock
from database.create_db import Database
from database.loader_LiveTrail import db_LiveTrail_loader
from database.load_features import empty_features, load_features

class TestFeaturesLoader(unittest.TestCase):

    def setUp(self):
        # Create a temporary SQLite database file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()  # Close the file so SQLite can use it

        # Connect to the SQLite database file
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Create tables required for testing
        self._create_tables()

    def _create_tables(self):
        # Create events table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                year TEXT,
                country TEXT
            )
        ''')

        # Create races table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS races (
                race_id TEXT,
                event_id INTEGER,
                race_name TEXT,
                distance REAL,
                elevation_pos INTEGER,
                elevation_neg INTEGER,
                departure_datetime TEXT,
                results_filepath TEXT,
                PRIMARY KEY (race_id, event_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id)
            )
        ''')

        # Create results table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                race_id TEXT,
                event_id INTEGER,
                position INTEGER,
                cat_position INTEGER,
                full_cat_position INTEGER,
                bib TEXT,
                surname TEXT,
                name TEXT,
                sex_category TEXT,
                full_category TEXT,
                time TEXT,
                PRIMARY KEY (race_id, event_id, bib),
                FOREIGN KEY (race_id) REFERENCES races(race_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id)
            )
        ''')

        # Create control points table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS control_points (
                control_point_id INTEGER PRIMARY KEY,
                event_id INTEGER,
                race_id INTEGER,
                code TEXT,
                name TEXT,
                distance REAL,
                elevation_pos INTEGER,
                elevation_neg INTEGER,
                FOREIGN KEY (race_id) REFERENCES races(race_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id),
                UNIQUE (event_id, race_id, code)
            )
        ''')

        # Create timing points table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS timing_points (
                timing_point_id INTEGER PRIMARY KEY,
                control_point_id INTEGER,
                race_id TEXT,
                event_id INTEGER,
                bib TEXT,
                time TEXT,
                FOREIGN KEY (control_point_id) REFERENCES control_points(control_point_id),
                FOREIGN KEY (race_id) REFERENCES races(race_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id),
                FOREIGN KEY (bib) REFERENCES results(bib),
                UNIQUE (control_point_id, bib)
            )
        ''')

        # Create model_input table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id TEXT,
                event_id INTEGER,
                bib TEXT,
                dist_total REAL,
                elevation_pos_total INTEGER,
                elevation_neg_total INTEGER,
                dist_segment REAL,
                dist_cumul REAL,
                elevation_pos_segment INTEGER,
                elevation_pos_cumul INTEGER,
                elevation_neg_segment INTEGER,
                elevation_neg_cumul INTEGER,
                time TEXT,
                FOREIGN KEY (race_id) REFERENCES races(race_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id),
                FOREIGN KEY (bib) REFERENCES results(bib)
            )
        ''')
        self.conn.close()

    def _insert_test_data(self):
        # Insert data into the 'features' table
        self.cursor.executemany('''
            INSERT INTO features (
                race_id,
                event_id,
                bib,
                dist_total,
                elevation_pos_total,
                elevation_neg_total,
                dist_segment,
                dist_cumul,
                elevation_pos_segment,
                elevation_pos_cumul,
                elevation_neg_segment,
                elevation_neg_cumul,
                time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            ('mim', 456, 603, 60.35, 3325, -2120, 8.47, 8.47, 357, 357, -235, -235, '00:58:30'),
            ('mim', 456, 603, 60.35, 3325, -2120, 14.60, 23.07, 693, 1050, -468, -703, '01:41:14')
        ])

        self.conn.commit()

    def tearDown(self):
        # Close the database connection after each test
        self.conn.close()
        # Remove the temporary database file
        os.remove(self.db_path)

    def test_empty_features(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._insert_test_data()
        self.cursor.execute('SELECT COUNT(*) FROM features')
        result = self.cursor.fetchone()[0]
        self.assertEqual(result, 2)
        self.conn.close()

        # Test the empty_features function
        empty_features(self.db_path)  # Pass the file path

        # Ensure the database is open before calling the function
        # Ensure the features table is empty
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('SELECT COUNT(*) FROM features')
        result = self.cursor.fetchone()[0]
        self.assertEqual(result, 0)

if __name__ == '__main__':
    unittest.main()
