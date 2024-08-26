import sqlite3
import pandas as pd
import datetime as dt
from database.create_db import Database


class Features:
    '''
    Features class
    '''
    # def __init__(self, event_id: int = None, race_id: str = None, bib: str = None, db: Database = None) -> None:
    def __init__(self, results_metadata: list[tuple[int, str, str]], db: Database = None) -> None:
        '''
        Args:
            results_metadata: Tuples containing (event_id, race_id, bib)
            db: App's database object
        '''
        if db is not None:
            self._db: Database = Database.create_database(db)
        else:
            self._db: Database = Database().create_database()
        # self._race_id: str = race_id
        # self._event_id: int = event_id
        # self._bib: str = bib
        self._results_metadata = results_metadata

    def fetch_features_table(self) -> pd.DataFrame:
        # Flatten list of tuples into a single list of parameters
        params = [item for sublist in self._results_metadata for item in sublist]

        # Construct the SQL query with the correct number of placeholders
        placeholders = ','.join(['(?, ?, ?)'] * len(self._results_metadata))
        query = f'''
            SELECT *
            FROM features
            WHERE (event_id, race_id, bib) IN ({placeholders})
        '''
        conn = sqlite3.connect(self._db.path)
        try:
            with conn:
                df = pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()
        return df

    @staticmethod
    def get_seconds(time: str) -> int:
        h, m, s = map(int, time.split(':'))
        return h * 3600 + m * 60 + s

    @staticmethod
    def format_time(seconds: int) -> str:
       return str(dt.timedelta(seconds=(seconds))).split('.')[0]
