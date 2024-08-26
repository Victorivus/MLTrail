'''
Viz test module for Results from the database
'''
import os
import sqlite3
import joblib
import streamlit as st
import pandas as pd
from ai.features import Features
from ai.xgboost import XGBoostRegressorModel

DATA_DIR_PATH = os.environ["DATA_DIR_PATH"]
DB_PATH = os.path.join(DATA_DIR_PATH, 'events.db')

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

def train_ai():
    if 'metadata_features' in st.session_state:
        metadata_features = st.session_state['metadata_features']
        with st.spinner('Converting table into model input...'):
            feat = Features(metadata_features, DB_PATH)
            data = feat.fetch_features_table().drop(columns=['id', 'race_id', 'event_id', 'bib'])
        with st.spinner('Training the model... This might take a while.'):
            rgs = XGBoostRegressorModel(df=data, target_column='time')
            rgs.train()  # Perform model training
        st.session_state['model_params'] = rgs.model.get_params()
        st.write("Model training completed.")
        st.warning('Head to "race results" page to predict racing time with your own-data AI model.')
        st.session_state.search_button_clicked = True
        return rgs
    else:
        st.write("Results data not found in session state.")
        return None

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

    # Don't know why, but we need to press twice the Reset button...
    # Check if the results are available in session state
    if st.session_state.results_df is not None or st.session_state.reset_button_clicked:
        st.write(st.session_state.results_df)
        if st.session_state.model_params is None:
            if st.button("Train AI model"):
                rgs = train_ai()
                st.session_state.ai_trained_button_clicked = True
                st.session_state.reset_button_clicked = False
                joblib.dump(rgs.model, os.path.join(DATA_DIR_PATH, 'model.pkl'))

    if st.session_state.model_params is not None and not st.session_state.reset_button_clicked:
        if not st.session_state.ai_trained_button_clicked:
            st.write("Model has already been trained. Parameters have been saved.")
        if st.button("Reset Model"):
            st.session_state.search_button_clicked = False
            st.session_state.reset_button_clicked = True
            st.session_state.model_params = None
            st.session_state.ai_trained_button_clicked = False
            st.write("Model has been reset. You can now train a new model.")

if __name__ == "__main__":
    main()
