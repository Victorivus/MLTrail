'''
Tests for front/auth.py: logging out must drop the whole session.
'''
import os
import unittest

from streamlit.testing.v1 import AppTest

FRONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "front")

# A page guarded by require_auth, as every app page is.
PAGE = f'''
import sys
sys.path.insert(0, {FRONT_DIR!r})
import streamlit as st
from auth import require_auth

if require_auth("unused.db"):
    st.write("private page for", st.session_state["user_id"])
'''


class TestLogout(unittest.TestCase):
    def test_logout_clears_all_session_state(self):
        at = AppTest.from_string(PAGE)
        at.session_state["logged_in"] = True
        at.session_state["user_id"] = 2
        at.session_state["username"] = "alice"
        at.session_state["search_results_df"] = "alice's search"
        at.session_state["gpx_track"] = "alice's course"
        at.run()
        self.assertFalse(at.exception)
        self.assertIn("private page for", at.markdown[0].value)

        at.sidebar.button[0].click().run()

        self.assertFalse(at.exception)
        for key in ("user_id", "username", "search_results_df", "gpx_track"):
            self.assertNotIn(key, at.session_state)
        self.assertFalse(at.session_state["logged_in"])
        self.assertEqual(at.title[0].value, "Login")


if __name__ == "__main__":
    unittest.main()
