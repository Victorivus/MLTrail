import unittest
import pytest
from database.loader_LiveTrail import db_LiveTrail_loader


pytestmark = pytest.mark.filterwarnings("ignore", message=".*XMLParsedAsHTMLWarning.*")

class Testdb_LiveTrail_loader(unittest.TestCase):
    """
    Test class for db_LiveTrail_loader
    """
    events = {
        'event1': 'Event One',
        'event2': 'Event Two',
        'event3': 'Event Three'
    }

    years_v1 = {
        'event1': ['2020', '2021'],  # exactly the same
        'event2': ['2019', '2020', '2021'],  # one new year
        'event3': ['2020']  # Extra event in years_v1
    }

    years_v2 = {
        'event1': ['2020', '2021'],  # exactly the same
        'event2': ['2019', '2020'],
    }

    def test_get_years_only_in_v1(self):
        expected_events = {'event2': 'Event Two', 'event3': 'Event Three'}
        expected_years = {'event2': ['2021'], 'event3': ['2020']}
        events, only_in_v1 = db_LiveTrail_loader.get_years_only_in_v1(self.events, self.years_v1, self.years_v2)

        self.assertEqual(events, expected_events)
        self.assertEqual(only_in_v1, expected_years)
