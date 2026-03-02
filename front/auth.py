"""Shared authentication module for Streamlit pages."""
import sqlite3
import bcrypt
import streamlit as st


def get_db_connection(db_path: str):
    """Get a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def authenticate_user(db_path: str, username: str, password: str):
    """Authenticate a user against the database."""
    conn = get_db_connection(db_path)
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return True, user
    return False, None


def login_page(db_path: str):
    """Display the login form."""
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_button = st.button("Login")

    if login_button:
        if username and password:
            success, user = authenticate_user(db_path, username, password)
            if success:
                st.success(f"Welcome, {user['username']}!")
                st.session_state['logged_in'] = True
                st.session_state['username'] = user['username']
                st.session_state['user_id'] = user['user_id']
                st.rerun()
            else:
                st.error("Invalid username or password.")
        else:
            st.warning("Please fill in both fields.")


def require_auth(db_path: str) -> bool:
    """Check authentication state. Returns True if logged in."""
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page(db_path)
        return False

    st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'logged_in': False}))
    return True
