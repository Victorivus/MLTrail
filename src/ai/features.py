import sqlite3
import pandas as pd
import datetime as dt
from database.create_db import Database


class Features:
    '''
    Features class
    '''
    # def __init__(self, event_id: int = None, race_id: str = None, bib: str = None, db: Database = None) -> None:
    def __init__(self, results_metadata: list[tuple[int, str, str]], db_path: str = None) -> None:
        '''
        Args:
            results_metadata: Tuples containing (event_id, race_id, bib)
            db: App's database object
        '''
        if db_path is not None:
            self._db: Database = Database.create_database(db_path)
        else:
            self._db: Database = Database().create_database()
        # self._race_id: str = race_id
        # self._event_id: int = event_id
        # self._bib: str = bib
        self._results_metadata = results_metadata

    def fetch_features_table(self) -> pd.DataFrame:
        if self._results_metadata[-1][-1] == "":
            self.fetch_anonymous_features_table()

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
    
    def fetch_anonymous_features_table(self) -> pd.DataFrame:
        # Flatten list of tuples into a single list of parameters
        params = [item for sublist in self._results_metadata for item in sublist[:-1]]

        # Construct the SQL query with the correct number of placeholders
        placeholders = ','.join(['(?, ?)'] * len(self._results_metadata))
        query = f'''
                    SELECT DISTINCT race_id, event_id, dist_total, elevation_pos_total, elevation_neg_total,
                        dist_segment, dist_cumul, elevation_pos_segment, elevation_pos_cumul, elevation_neg_segment,
                        elevation_neg_cumul
                    FROM features
                    WHERE (event_id, race_id) IN ({placeholders})
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
