'''
    MLTrail Results Database creation
'''
import os
import logging
import sqlite3
import bcrypt
from sqlite3 import Connection, Cursor

logger = logging.getLogger(__name__)

VALID_TABLES = frozenset({
    'users', 'events', 'races', 'results',
    'control_points', 'timing_points', 'features',
    'user_results'
})


class Database:
    '''
        SQLite3 Database for storing locally racing data.
    '''
    path: str = 'events.db'

    @classmethod
    def create_database(cls, path=None) -> 'Database':
        '''
            Create app's SQLite database
        '''
        if path:
            cls.path = path

        # Check if the database file already exists
        if os.path.exists(cls.path):
            logger.info("Database already exists at %s", cls.path)
            return cls

        # Connect to SQLite database (creates if not exists)
        conn: Connection = sqlite3.connect(cls.path)
        cursor: Cursor = conn.cursor()

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
        ''')

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

        # Create races table. cat_needs_backfill flags races whose category
        # data is absent or partial in LiveTrail's bulk XML and must be
        # recovered per-runner from coureur.php.
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
                cat_needs_backfill INTEGER NOT NULL DEFAULT 0,
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

        # Create user_results table: per-user set of results they've claimed as theirs.
        # include_in_training toggles whether a row feeds the personal model (soft-delete).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_results (
                user_id INTEGER,
                event_id INTEGER,
                race_id TEXT,
                bib TEXT,
                include_in_training INTEGER NOT NULL DEFAULT 1,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, event_id, race_id, bib),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (event_id) REFERENCES events(event_id),
                FOREIGN KEY (race_id) REFERENCES races(race_id)
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

        logger.info("Database created successfully at %s", cls.path)

        return cls

    @classmethod
    def ensure_cat_backfill_column(cls, path=None) -> None:
        '''
            Idempotent migration: add races.cat_needs_backfill if it is missing.

            Older DBs predate the scraped-category-gap feature; SQLite does not
            support `ADD COLUMN IF NOT EXISTS`, so inspect pragma first.
        '''
        if path:
            cls.path = path
        try:
            conn = sqlite3.connect(cls.path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(races)")
            existing = {row[1] for row in cursor.fetchall()}
            if 'cat_needs_backfill' not in existing:
                cursor.execute(
                    "ALTER TABLE races ADD COLUMN "
                    "cat_needs_backfill INTEGER NOT NULL DEFAULT 0"
                )
                conn.commit()
                logger.info("Added races.cat_needs_backfill column")
            conn.close()
        except sqlite3.Error as e:
            logger.error("Error ensuring cat_needs_backfill column: %s", e)

    @classmethod
    def ensure_user_results_table(cls, path=None) -> None:
        '''
            Idempotent migration for existing DBs that predate the user_results table.
        '''
        if path:
            cls.path = path
        try:
            conn = sqlite3.connect(cls.path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_results (
                    user_id INTEGER,
                    event_id INTEGER,
                    race_id TEXT,
                    bib TEXT,
                    include_in_training INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, event_id, race_id, bib),
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (event_id) REFERENCES events(event_id),
                    FOREIGN KEY (race_id) REFERENCES races(race_id)
                )
            ''')
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error("Error ensuring user_results table: %s", e)

    @classmethod
    def empty_all_tables(cls, path=None):
        '''
            Empty all database's tables
        '''
        if path:
            cls.path = path
        try:
            conn = sqlite3.connect(cls.path)
            cursor = conn.cursor()

            # Get a list of all tables in the database
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            # Iterate over each table and delete all rows
            for table in tables:
                table_name = table[0]
                if table_name in VALID_TABLES:
                    cursor.execute(f"DELETE FROM {table_name};")
                else:
                    logger.warning("Skipping unknown table: %s", table_name)

            conn.commit()
            conn.close()
            logger.info("All tables have been emptied successfully.")
        except sqlite3.Error as e:
            logger.error("Error emptying tables: %s", e)

    @classmethod
    def create_user(cls, username, plain_password, email=None, path=None):
        if path:
            cls.path = path
        if email is None:
            email = f"{username}@mltrail.local"
        try:
            conn = sqlite3.connect(cls.path)
            cursor = conn.cursor()
            hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username, email, hashed_password))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error("Error creating user: %s", e)
