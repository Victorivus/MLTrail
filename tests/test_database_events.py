import os
import unittest
import sqlite3
from unittest.mock import patch
from database.create_db import Database
from database.database import Event

# We use results from previous tests for the following ones,
# i.e. when inserting events in the DB and then modifying them 
# This tests will be named *_records_[letter]_* since unittest
# executes tests alphabetically


class TestEvent(unittest.TestCase):
    db: Database = Database.create_database(path='test.db')

    def test_get_event_id(self):
        event = Event(db=self.db)
        event._set_event_id(1)
        self.assertEqual(event.get_event_id(), 1)

    def test_get_event_name(self):
        event = Event(db=self.db)
        event.set_event_name("Test Event")
        self.assertEqual(event.get_event_name(), "Test Event")

    def test_get_date(self):
        event = Event(db=self.db)
        event.set_date("2024-01-01")
        self.assertEqual(event.get_date(), "2024-01-01")

    def test_get_country(self):
        event = Event(db=self.db)
        event.set_country("USA")
        self.assertEqual(event.get_country(), "USA")

    def test_records_a_save_to_database_insert(self):
        event = Event(db=self.db)
        event.set_event_name("Test Event")
        event.set_date("2024-01-01")
        event.set_country("USA")
        event.save_to_database()
        conn = sqlite3.connect(self.db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM events WHERE event_name = "Test Event" AND date = "2024-01-01" AND country = "USA"')
            row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[1], "Test Event")
        self.assertEqual(row[2], "2024-01-01")
        self.assertEqual(row[3], "USA")

    def test_records_b_get_event_id_from_database(self):
        event = Event(event_name="Test Event bis",
                      date="2024-01-01",
                      country="FRA",
                      db=self.db)
        event.save_to_database()
        conn = sqlite3.connect(self.db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT event_id FROM events WHERE event_name="Test Event bis"')
            row = cursor.fetchone()
        self.assertEqual(event.get_event_id_from_database(), row[0])

    def test_records_c_save_to_database_update(self):
        event = Event(event_name="Test Event",
                      date="2024-01-01",
                      country="USA",
                      db=self.db)
        event_id = event.get_event_id()
        event.set_country("UK")
        event.save_to_database()
        conn = sqlite3.connect(self.db.path)
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM events WHERE event_name = "Test Event"')
            row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], event_id)
        self.assertEqual(row[3], "UK")

    @patch('sqlite3.connect')
    def test_load_from_database(self, mock_connect):
        mock_cursor = mock_connect.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = ("Test Event", "2024-01-01", "USA")
        event = Event.load_from_database(1, db=self.db)
        self.assertIsNotNone(event)
        self.assertEqual(event.get_event_name(), "Test Event")
        self.assertEqual(event.get_date(), "2024-01-01")
        self.assertEqual(event.get_country(), "USA")


if __name__ == '__main__':
    unittest.main()
