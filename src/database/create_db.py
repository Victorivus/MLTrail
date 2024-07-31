'''
    MLTrail Results Database creation
'''
import os
import sqlite3
from sqlite3 import Connection, Cursor


class Database:
    '''
        SQLite3 Database for storing locally racing data.
    '''
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
            print(f"INFO: {cls.path}")
            print("INFO: Database already exists.")
            return cls

        # Connect to SQLite database (creates if not exists)
        conn: Connection = sqlite3.connect(cls.path)
        cursor: Cursor = conn.cursor()

        # Create events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                year TEXT,
                country TEXT
            )
        ''')

        # Create races table
        cursor.execute('''
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
        cursor.execute('''
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
        cursor.execute('''
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
        cursor.execute('''
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
        cursor.execute('''
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

        # Commit changes and close connection
        conn.commit()
        conn.close()

        print("Database created successfully.")

        return cls

    @classmethod
    def empty_all_tables(cls, path=None):
        '''
            Empty all database's tables
        '''
        if path:
            cls.path = path
        try:
            # Connect to the database
            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            # Get a list of all tables in the database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            # Iterate over each table and delete all rows
            for table in tables:
                table_name = table[0]
                cursor.execute(f"DELETE FROM {table_name};")

            # Commit changes and close connection
            conn.commit()
            conn.close()
            print("INFO: All tables have been emptied successfully.")
        except sqlite3.Error as e:
            print("ERROR: ", e)
