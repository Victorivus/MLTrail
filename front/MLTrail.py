"""MLTrail - Trail Race Analysis and ML Predictions"""
import streamlit as st
from config import get_config
from auth import require_auth

cfg = get_config()
DB_PATH = cfg.db_path

st.set_page_config(
    page_title="ML Trail",
    page_icon="🏃🏼🤖",
)

if not require_auth(DB_PATH):
    st.stop()

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
