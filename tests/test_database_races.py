import unittest
import sqlite3
from database.create_db import Database
from database.database import Race

# We use results from previous tests for the following ones,
# i.e. when inserting events in the DB and then modifying them 
# This tests will be named *_records_[letter]_* since unittest
# executes tests alphabetically


class TestEvent(unittest.TestCase):
    db: Database = Database.create_database(path='test.db')

    def test_init(self):
        race = Race(race_id=1, event_id=1, race_name="Test Race", distance=10.5,
                    elevation_pos=100, elevation_neg=50, departure_datetime="2024-01-01 09:00:00",
                    results_filepath="/path/to/results.csv", db=self.db)
        self.assertEqual(race.get_race_id(), 1)
        self.assertEqual(race.get_event_id(), 1)
        self.assertEqual(race.get_race_name(), "Test Race")
        self.assertEqual(race.get_distance(), 10.5)
        self.assertEqual(race.get_elevation_pos(), 100)
        self.assertEqual(race.get_elevation_neg(), 50)
        self.assertEqual(race.get_departure_datetime(), "2024-01-01 09:00:00")
        self.assertEqual(race.get_results_filepath(), "/path/to/results.csv")

    def test_setters_and_getters(self):
        race = Race(db=self.db)
        race.set_race_id(1)
        race.set_event_id(1)
        race.set_race_name("Test Race")
        race.set_distance(10.5)
        race.set_elevation_pos(100)
        race.set_elevation_neg(50)
        race.set_departure_datetime("2024-01-01 09:00:00")
        race.set_results_filepath("/path/to/results.csv")
        self.assertEqual(race.get_race_id(), 1)
        self.assertEqual(race.get_event_id(), 1)
        self.assertEqual(race.get_race_name(), "Test Race")
        self.assertEqual(race.get_distance(), 10.5)
        self.assertEqual(race.get_elevation_pos(), 100)
        self.assertEqual(race.get_elevation_neg(), 50)
        self.assertEqual(race.get_departure_datetime(), "2024-01-01 09:00:00")
        self.assertEqual(race.get_results_filepath(), "/path/to/results.csv")

    def test_save_to_database(self):
        # Create a Race object
        race = Race(race_id=1, event_id=1, race_name="Test Race", distance=10.5,
                    elevation_pos=100, elevation_neg=50, departure_datetime="2024-01-01 09:00:00",
                    results_filepath="/path/to/results.csv", db=self.db)
        # Save it to the database
        race.save_to_database()
        # Retrieve it from the database and compare
        # retrieved_race = Race.load_from_database(event_id=1, race_id=1, db=self.db)
        retrieved_race = None
        event_id = 1
        race_id = 1
        conn = sqlite3.connect(self.db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT race_name, distance, elevation_pos, elevation_neg, departure_datetime, results_filepath
                FROM races WHERE event_id = ? AND race_id = ?
            ''', (event_id, race_id,))
            row = cursor.fetchone()
        conn.close()
        if row:
            retrieved_race = Race(event_id=event_id, race_id=race_id, race_name=row[0],
                                  distance=row[1], elevation_pos=row[2], elevation_neg=row[3],
                                  departure_datetime=row[4], results_filepath=row[5])
        self.assertIsNotNone(retrieved_race)
        self.assertEqual(race.get_race_id(), retrieved_race.get_race_id())
        self.assertEqual(race.get_event_id(), retrieved_race.get_event_id())
        self.assertEqual(race.get_race_name(), retrieved_race.get_race_name())
        self.assertEqual(race.get_distance(), retrieved_race.get_distance())
        self.assertEqual(race.get_elevation_pos(), retrieved_race.get_elevation_pos())
        self.assertEqual(race.get_elevation_neg(), retrieved_race.get_elevation_neg())
        self.assertEqual(race.get_departure_datetime(), retrieved_race.get_departure_datetime())
        self.assertEqual(race.get_results_filepath(), retrieved_race.get_results_filepath())


if __name__ == '__main__':
    unittest.main()