'''
    MLTrail Results Database creation
'''
import os
import sqlite3
from sqlite3 import Connection, Cursor


class Database:
    path: str = 'events.db'

    @classmethod
    def create_database(cls, path=None) -> Connection:
        '''
            Create app's SQLite database
        '''
        if path:
            cls.path = path

        # Check if the database file already exists
        if os.path.exists(cls.path):
            print("Database already exists.")
            return cls

        # Connect to SQLite database (creates if not exists)
        conn: Connection = sqlite3.connect(cls.path)
        cursor: Cursor = conn.cursor()

        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY,
                event_code TEXT,
                event_name TEXT,
                year TEXT,
                country TEXT
            )
        ''')

        # Create races table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS races (
                race_id INTEGER,
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                race_id INTEGER,
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
                PRIMARY KEY (race_id, event_id),
                FOREIGN KEY (race_id) REFERENCES races(race_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id)
            )
        ''')

        # Commit changes and close connection
        conn.commit()
        conn.close()

        print("Database created successfully.")

        return cls
