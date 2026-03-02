"""Personal Results and AI Model Training page."""
import time
import logging
import sqlite3
import streamlit as st
import pandas as pd
from config import get_config
from auth import require_auth
from ai.training_service import TrainingState, TrainingStatus, start_background_training

logger = logging.getLogger(__name__)

cfg = get_config()
DATA_DIR_PATH = cfg.data_dir_path
DB_PATH = cfg.db_path

if not require_auth(DB_PATH):
    st.stop()


def fetch_distinct_names():
    '''
    Function to fetch distinct surnames and names from the database
    '''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT surname, name FROM results")
    names = [f"{row[0]}, {row[1]}" for row in cursor.fetchall()]
    conn.close()
    return names


def fetch_results(surname, first_name=None):
    '''
    Function to execute query and fetch results
    '''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if first_name is None and ',' not in surname:
        query = """
            SELECT results.event_id, results.race_id, results.bib, events.name, events.year, results.race_id, results.position, results.cat_position,
                    results.full_cat_position, results.surname, results.name,
                    results.sex_category, results.full_category, results.time
            FROM results
            INNER JOIN events ON
                events.event_id = results.event_id
            WHERE LOWER(results.surname) LIKE ?
        """
        cursor.execute(query, ('%' + surname.lower() + '%',))
    else:
        if ',' in surname:
            surname, first_name = [part.strip() for part in surname.split(",")]
        query = """
            SELECT results.event_id, results.race_id, results.bib, events.name, events.year, races.race_name, results.position, results.cat_position,
                    results.full_cat_position, results.surname, results.name,
                    results.sex_category, results.full_category, results.time
            FROM results
            INNER JOIN events ON
                events.event_id = results.event_id
            INNER JOIN races ON
                races.race_id = results.race_id
                AND races.event_id = results.event_id
            WHERE LOWER(results.surname) LIKE ?
                    AND LOWER(results.name) LIKE ?
        """
        cursor.execute(query, (surname.lower(), first_name.lower()))

    results = cursor.fetchall()
    conn.close()
    return results


def main():
    '''
    Main function for the Streamlit page
    '''
    st.set_page_config(layout="wide")
    st.title("Trail Race Results Lookup")
    st.markdown("*Scraped from LiveTrail up to 04/08/2024.*")

    # Initialize session state variables if they don't exist
    if 'search_button_clicked' not in st.session_state:
        st.session_state.search_button_clicked = False
    if 'results_df' not in st.session_state:
        st.session_state.results_df = None
    if 'model_params' not in st.session_state:
        st.session_state.model_params = None
    if 'ai_trained_button_clicked' not in st.session_state:
        st.session_state.ai_trained_button_clicked = False
    if 'reset_button_clicked' not in st.session_state:
        st.session_state.reset_button_clicked = False
    if 'training_state' not in st.session_state:
        st.session_state.training_state = TrainingState()

    # User input for surname
    surname = st.text_input("Enter your `surname` or `surname, name`:")

    # Button to fetch results
    if st.button("Search"):
        with st.spinner('Searching...'):
            if surname:
                results = fetch_results(surname)
                if results:
                    results_df = pd.DataFrame(results, columns=["event_id", "race_id", "bib", "Event", "Year", "Race",
                                                                "Position", "Sex Position", "Category Position", "Surname",
                                                                "Name", "Sex Category", "Full Category", "Time"])
                    st.session_state.results_df = results_df
                    metadata = results_df[["event_id", "race_id", "bib"]]
                    metadata = list(metadata.itertuples(index=False, name=None))
                    st.session_state['metadata_features'] = metadata
                    st.session_state.search_button_clicked = True
                else:
                    st.error("No results found for the provided surname.")
            else:
                st.warning("Please enter your surname.")

    # Check if the results are available in session state
    if st.session_state.results_df is not None or st.session_state.reset_button_clicked:
        st.write(st.session_state.results_df)

        training_state = st.session_state.training_state

        if st.session_state.model_params is None:
            # Handle background training states
            if training_state.is_running:
                st.info(f"**{training_state.progress_message}**")
                elapsed = training_state.elapsed_seconds
                st.progress(min(elapsed / 120.0, 0.99),
                           text=f"Elapsed: {elapsed:.0f}s")
                time.sleep(2)
                st.rerun()
            elif training_state.status == TrainingStatus.COMPLETED:
                st.success(training_state.progress_message)
                st.session_state.model_params = training_state.model_params
                st.session_state.ai_trained_button_clicked = True
                st.session_state.training_state = TrainingState()  # reset
                st.rerun()
            elif training_state.status == TrainingStatus.FAILED:
                st.error(f"Training failed: {training_state.error_message}")
                st.session_state.training_state = TrainingState()  # reset for retry
            else:
                if st.button("Train AI model"):
                    if 'metadata_features' in st.session_state:
                        start_background_training(
                            state=training_state,
                            metadata_features=st.session_state['metadata_features'],
                            db_path=DB_PATH,
                            model_save_path=cfg.model_path,
                        )
                        st.rerun()
                    else:
                        st.write("Results data not found in session state.")

    if st.session_state.model_params is not None and not st.session_state.reset_button_clicked:
        if not st.session_state.ai_trained_button_clicked:
            st.write("Model has already been trained. Parameters have been saved.")
        st.success("Model trained! Head to **Race Results** page to predict racing time with your AI model.")
        if st.button("Reset Model"):
            st.session_state.search_button_clicked = False
            st.session_state.reset_button_clicked = True
            st.session_state.model_params = None
            st.session_state.ai_trained_button_clicked = False
            st.session_state.training_state = TrainingState()
            st.write("Model has been reset. You can now train a new model.")

if __name__ == "__main__":
    main()
