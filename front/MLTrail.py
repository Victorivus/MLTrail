'''
Viz test module for the Results class
'''
import os
import bcrypt
import streamlit as st
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv(override=True)

DATA_DIR_PATH = os.environ["DATA_DIR_PATH"]
DB_PATH = os.path.join(DATA_DIR_PATH, 'events.db')

# Function to store session-like data using Streamlit's caching mechanism
@st.cache_data(hash_funcs={dict: lambda _: None})
def get_session_data():
    '''
        Get session data function
    '''
    return {}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    login_page()
else:
    st.sidebar.button("Logout", on_click=lambda: st.session_state.update({'logged_in': False}))
    st.write(f"Hello, {st.session_state['username']}! Welcome back.")
    st.write("Your app's main content goes here.")

st.set_page_config(
    page_title="ML Trail",
    page_icon="🏃🏼🤖",
)

st.write("# Welcome to ML Trail! 🏃🏼🤖")

st.sidebar.success("Select a page above.")

st.markdown('''
            ML Trail is your ultimate destination for trail race results and advanced analysis. Whether you're an avid trail runner, a race organizer, or just someone interested in the world of trail running, ML Trail has something for you.

            ## What We Offer
            - **Trail Race Results:** Access comprehensive race results from various trail races around the world.
            - **Advanced Analysis:** Dive deep into race data with advanced analysis tools and visualizations.
            - **Collaboration:** We're open to collaboration! Check out our [GitHub repository](https://github.com/Victorivus/MLTrail) to contribute to the project.

            ## Why Choose ML Trail?
            - **Accuracy:** Our race results are accurate and up-to-date, ensuring you have the latest information.
            - **Insightful Analysis:** Gain valuable insights into race performance, trends, and patterns with our advanced analysis tools.
            - **Community:** Join our growing community of trail runners and data enthusiasts to share knowledge and experiences.

            ## Get Started
            Ready to explore the world of trail running with ML Trail? Visit our website and start exploring today!

            '''
            )

# Database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)  # Replace with your database file
    conn.row_factory = sqlite3.Row
    return conn

# Function to authenticate user
def authenticate_user(username, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return True, user
    return False, None

# Streamlit app
def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_button = st.button("Login")
    
    if login_button:
        if username and password:
            success, user = authenticate_user(username, password)
            if success:
                st.success(f"Welcome, {user['username']}!")
                st.session_state['logged_in'] = True
                st.session_state['username'] = user['username']
                st.session_state['user_id'] = user['user_id']
            else:
                st.error("Invalid username or password.")
        else:
            st.warning("Please fill in both fields.")
