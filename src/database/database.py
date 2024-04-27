import sqlite3
from sqlite3 import Connection
from typing import Union
from database.create_db import Database


class Event:
    def __init__(self, event_name: str = None, date: str = None,
                 country: str = None, db: Database = None) -> None:
        if db is not None:
            self._db: Database = db
        else:
            self._db: Database = Database().create_database()
        self._event_name: str = event_name
        self._date: str = date
        self._country: str = country
        self._event_id: int = self.get_event_id_from_database()

    def __str__(self):
        return f"Event ID: {self._event_id}, Name: {self._event_name}, Date: {self._date}, Country: {self._country}"

    def _set_event_id(self, event_id) -> None:
        self._event_id = event_id

    def get_event_id(self) -> int:
        return self._event_id

    def set_event_name(self, event_name) -> None:
        self._event_name = event_name

    def get_event_name(self) -> str:
        return self._event_name

    def set_date(self, date) -> None:
        self._date = date

    def get_date(self) -> str:
        return self._date

    def set_country(self, country) -> None:
        self._country = country

    def get_country(self) -> str:
        return self._country

    def save_to_database(self) -> None:
        conn = sqlite3.connect(self._db.path)
        with conn:
            cursor = conn.cursor()
            if self._event_id is None:
                self._set_event_id(self.get_event_id_from_database())
                if self._event_id is None:
                    cursor.execute('INSERT INTO events (event_name, date, country) VALUES (?, ?, ?)',
                                   (self._event_name, self._date, self._country))
                else:
                    cursor.execute('''
                        UPDATE events
                        SET event_name = ?, date = ?, country = ?
                        WHERE event_id = ?
                    ''', (self._event_name, self._date, self._country, self._event_id))
            else:
                cursor.execute('''
                    UPDATE events
                    SET event_name = ?, date = ?, country = ?
                    WHERE event_id = ?
                ''', (self._event_name, self._date, self._country, self._event_id))
            conn.commit()
        conn.close()
        # Update event_id after setting it in db
        self._set_event_id(self.get_event_id_from_database())

    def get_event_id_from_database(self) -> int | None:
        conn = sqlite3.connect(self._db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT event_id FROM events WHERE event_name = ? AND date = ? AND country = ?',
                        (self._event_name, self._date, self._country,))
            row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
        return None

    @staticmethod
    def load_from_database(event_id, db: Database = None) -> Union['Event', None]:
        if db is None:
            conn = sqlite3.connect(Database().path)
        else:
            conn = sqlite3.connect(db.path)
        cursor = conn.cursor()
        cursor.execute('SELECT event_name, date, country FROM events WHERE event_id = ?',
                       (event_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            event = Event()
            event._set_event_id(event_id)
            event.set_event_name(row[0])
            event.set_date(row[1])
            event.set_country(row[2])
            return event
        return None


class Race:
    def __init__(self, race_id: int = None, event_id: int = None, race_name: str = None,
                 distance: float = None, elevation_pos: int = None, elevation_neg: int = None,
                 departure_datetime: str = None, results_filepath: str = None, db: Database = None) -> None:
        if db is not None:
            self._db: Database = db
        else:
            self._db: Database = Database().create_database()
        self._race_id: int = race_id
        self._event_id: int = event_id
        self._race_name: str = race_name
        self._distance: float = distance
        self._elevation_pos: int = elevation_pos
        self._elevation_neg: int = elevation_neg
        self._departure_datetime: str = departure_datetime
        self._results_filepath: str = results_filepath

    def __str__(self):
        return f"Race ID: {self._race_id}, Event ID: {self._event_id}, Name: {self._race_name},\
                Distance: {self._distance}, Elevation Pos: {self._elevation_pos}, Elevation Neg:\
                {self._elevation_neg}, Departure Datetime: {self._departure_datetime}, Results Filepath: {self._results_filepath}"

    def set_race_id(self, race_id) -> None:
        self._race_id = race_id

    def get_race_id(self) -> int:
        return self._race_id

    def set_event_id(self, event_id) -> None:
        self._event_id = event_id

    def get_event_id(self) -> int:
        return self._event_id

    def set_race_name(self, race_name) -> None:
        self._race_name = race_name

    def get_race_name(self) -> str:
        return self._race_name

    def set_distance(self, distance) -> None:
        self._distance = distance

    def get_distance(self) -> float:
        return self._distance

    def set_elevation_pos(self, elevation_pos) -> None:
        self._elevation_pos = elevation_pos

    def get_elevation_pos(self) -> int:
        return self._elevation_pos

    def set_elevation_neg(self, elevation_neg) -> None:
        self._elevation_neg = elevation_neg

    def get_elevation_neg(self) -> int:
        return self._elevation_neg

    def set_departure_datetime(self, departure_datetime) -> None:
        self._departure_datetime = departure_datetime

    def get_departure_datetime(self) -> str:
        return self._departure_datetime

    def set_results_filepath(self, results_filepath) -> None:
        self._results_filepath = results_filepath

    def get_results_filepath(self) -> str:
        return self._results_filepath

    def save_to_database(self) -> None:
        conn = sqlite3.connect(self._db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO races (event_id, race_name, distance, elevation_pos,
                                    elevation_neg, departure_datetime, results_filepath)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (self._event_id, self._race_name, self._distance, self._elevation_pos,
                self._elevation_neg, self._departure_datetime, self._results_filepath))
            conn.commit()
        conn.close()

    @staticmethod
    def get_race_event_id_from_database(event_id, race_name, db: Database = None):
        if db is None:
            conn = sqlite3.connect(Database().path)
        else:
            conn = sqlite3.connect(db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT race_id FROM races WHERE event_id = ? AND race_name = ?',
                           (event_id, race_name,))
            row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
        return None

    @staticmethod
    def load_from_database(event_id, race_id, db: Database = None) -> Union['Race', None]:
        if db is None:
            conn = sqlite3.connect(Database().path)
        else:
            conn = sqlite3.connect(db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT race_name, distance, elevation_pos, elevation_neg, departure_datetime, results_filepath
                FROM races WHERE event_id = ? AND race_id = ?
            ''', (event_id, race_id,))
            row = cursor.fetchone()
        conn.close()
        if row:
            race = Race(event_id=event_id, race_id=race_id, race_name=row[0],
                        distance=row[1], elevation_pos=row[2], elevation_neg=row[3],
                        departure_datetime=row[4], results_filepath=row[5])
            return race
        return None


class Results:
    _db_path: str = Database().path

    def __init__(self, race_id: int = None, event_id: int = None, position: int = None,
                 cat_position: int = None, full_cat_position: int = None, bib: int = None,
                 surname: str = None, name: str = None, sex_category: str = None,
                 full_category: str = None, time: str = None, db: Database = None) -> None:
        if db is not None:
            self._db: Database = db
        else:
            self._db: Database = Database().create_database()
        self._race_id: int = race_id
        self._event_id: int = event_id
        self._position: int = position
        self._cat_position: int = cat_position
        self._full_cat_position: int = full_cat_position
        self._bib: int = bib
        self._surname: str = surname
        self._name: str = name
        self._sex_category: str = sex_category
        self._full_category: str = full_category
        self._time: str = time

    def __str__(self) -> str:
        return f" Event ID: {self._event_id}, Race ID: {self._race_id}, Participants: {self.count_bib()}, Women participants: {round(100*self.count_category()/self.count_bib())}%, Finishers: {self.count_time()}"

    def set_race_id(self, race_id) -> None:
        self._race_id = race_id

    def get_race_id(self) -> int:
        return self._race_id

    def set_event_id(self, event_id) -> None:
        self._event_id = event_id

    def get_event_id(self) -> int:
        return self._event_id

    def set_position(self, position) -> None:
        self._position = position

    def get_position(self) -> int:
        return self._position

    def set_cat_position(self, cat_position) -> None:
        self._cat_position = cat_position

    def get_cat_position(self) -> int:
        return self._cat_position

    def set_full_cat_position(self, full_cat_position) -> None:
        self._full_cat_position = full_cat_position

    def get_full_cat_position(self) -> int:
        return self._full_cat_position

    def set_bib(self, bib) -> None:
        self._bib = bib

    def get_bib(self) -> int:
        return self._bib

    def set_surname(self, surname) -> None:
        self._surname = surname

    def get_surname(self) -> str:
        return self._surname

    def set_name(self, name) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def set_sex_category(self, sex_category) -> None:
        self._sex_category = sex_category

    def get_sex_category(self) -> str:
        return self._sex_category

    def set_full_category(self, full_category) -> None:
        self._full_category = full_category

    def get_full_category(self) -> str:
        return self._full_category

    def set_time(self, time) -> None:
        self._time = time

    def get_time(self) -> str:
        return self._time

    def save_to_database(self) -> None:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO results (race_id, event_id, position, cat_position, full_cat_position, bib, surname, name, sex_category, full_category, time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self._race_id, self._event_id, self._position, self._cat_position, self._full_cat_position, self._bib, self._surname, self._name, self._sex_category, self._full_category, self._time))
        conn.commit()
        conn.close()

    def count_bib(self) -> int:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(bib) FROM results WHERE event_id = ? AND race_id = ? AND bib IS NOT NULL AND bib != ''
        ''', (self._event_id, self._race_id))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def count_category(self, category='Female') -> int:
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT COUNT(*) FROM results WHERE event_id = ? AND race_id = ? AND
                        sex_category = ? AND full_category IS NOT NULL AND full_category != ''
                       ''', (self._event_id, self._race_id, category))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def count_time(self, db_path: str = 'events.db') -> int:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(time) FROM results WHERE event_id = ? AND race_id = ? AND time IS NOT NULL AND time != ''
        ''', (self._event_id, self._race_id))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def load_from_database(race_id, event_id, db: Database = None) -> Union['Results', None]:
        if db is None:
            conn = sqlite3.connect(Database().path)
        else:
            conn = sqlite3.connect(db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT position, cat_position, full_cat_position, bib, surname, name, sex_category, full_category, time
                FROM results WHERE race_id = ? AND event_id = ?
            ''', (race_id, event_id,))
            row = cursor.fetchone()
            conn.close()
        if row:
            results = Results(
                race_id=race_id,
                event_id=event_id,
                position=row[0],
                cat_position=row[1],
                full_cat_position=row[2],
                bib=row[3],
                surname=row[4],
                name=row[5],
                sex_category=row[6],
                full_category=row[7],
                time=row[8]
            )
            return results
        return None
