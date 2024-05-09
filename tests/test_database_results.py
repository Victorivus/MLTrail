import unittest
import sqlite3
import pytest
from database.create_db import Database
from database.database import Results

pytestmark = pytest.mark.filterwarnings("ignore", message=".*XMLParsedAsHTMLWarning.*")


class TestResults(unittest.TestCase):
    db: Database = Database.create_database(path='test.db')

    def test_init(self):
        results = Results(race_id=1, event_id=1, position=1, cat_position=1, full_cat_position=1,
                          bib=123, surname="Doe", name="John", sex_category="Male",
                          full_category="Senior", time="1:23:45", db=self.db)
        self.assertEqual(results.get_race_id(), 1)
        self.assertEqual(results.get_event_id(), 1)
        self.assertEqual(results.get_position(), 1)
        self.assertEqual(results.get_cat_position(), 1)
        self.assertEqual(results.get_full_cat_position(), 1)
        self.assertEqual(results.get_bib(), 123)
        self.assertEqual(results.get_surname(), "Doe")
        self.assertEqual(results.get_name(), "John")
        self.assertEqual(results.get_sex_category(), "Male")
        self.assertEqual(results.get_full_category(), "Senior")
        self.assertEqual(results.get_time(), "1:23:45")

    def test_save_to_database(self):
        # Create a Results object
        results = Results(race_id=1, event_id=1, position=1, cat_position=1, full_cat_position=1,
                          bib=123, surname="Doe", name="John", sex_category="Male",
                          full_category="Senior", time="1:23:45", db=self.db)
        # Save it to the database
        results.save_to_database()
        # Retrieve it from the database and compare
        retrieved_results = Results.load_from_database(race_id=1, event_id=1, db=self.db)
        self.assertEqual(results.get_race_id(), retrieved_results.get_race_id())
        self.assertEqual(results.get_event_id(), retrieved_results.get_event_id())
        self.assertEqual(results.get_position(), retrieved_results.get_position())
        self.assertEqual(results.get_cat_position(), retrieved_results.get_cat_position())
        self.assertEqual(results.get_full_cat_position(), retrieved_results.get_full_cat_position())
        self.assertEqual(results.get_bib(), int(retrieved_results.get_bib()))
        self.assertEqual(results.get_surname(), retrieved_results.get_surname())
        self.assertEqual(results.get_name(), retrieved_results.get_name())
        self.assertEqual(results.get_sex_category(), retrieved_results.get_sex_category())
        self.assertEqual(results.get_full_category(), retrieved_results.get_full_category())
        self.assertEqual(results.get_time(), retrieved_results.get_time())

if __name__ == '__main__':
    unittest.main()