'''
Viz test module for Results from the database
'''
import os
import sqlite3
import streamlit as st
import pandas as pd
from ai.features import Features

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
    # Connect to SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if first_name is None and ',' not in surname:
        # Execute query to retrieve results
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
        # Execute query to retrieve results
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

    # Close database connection
    conn.close()

    return results


def main():
    '''
    main function for the Streamlit page
    '''
    st.set_page_config(layout="wide")
    st.title("Trail Race Results Lookup")
    st.markdown("*Scraped from LiveTrail up to 04/08/2024.*")
    if 'result_button_clicked' not in st.session_state:
        st.session_state.result_button_clicked = False
    # Fetch distinct surnames and names from the database
    # Too long, it lags.
    # names = fetch_distinct_names()

    # User input for surname
    surname = st.text_input("Enter your `surname` or `surname, name`:")

    # Button to fetch results
    if st.button("Search by free text"):
        # Check if surname is provided
        if surname:
            # Fetch results from database
            results = fetch_results(surname)

            # Display results in table
            if results:
                results = pd.DataFrame(fetch_results(surname), columns=["event_id", "race_id", "bib", "Event", "Year", "Race",
                                                                        "Position", "Sex Position",
                                                                        "Category Position", "Surname",
                                                                        "Name", "Sex Category",
                                                                        "Full Category", "Time"])
                
                metadata = results[["event_id", "race_id", "bib"]]
                metadata = list(metadata.itertuples(index=False, name=None))
                results = results.drop(columns=["event_id", "race_id", "bib"])
                st.session_state['metadata_features'] = metadata
                st.write(results)
                st.session_state.result_button_clicked = True
            else:
                st.error("No results found for the provided surname.")
        else:
            st.warning("Please enter your surname.")

    if st.session_state.result_button_clicked:
        if st.button("Convert to model input"):
            if 'metadata_features' in st.session_state:
                metadata_features = st.session_state['metadata_features']
                feat = Features(metadata_features, DB_PATH)
                st.write(feat.fetch_features_table())
            else:
                st.write("Results data not found in session state.")
            st.warning("Not implemented yet. Feature copming soon...")

    # name = st.selectbox("Select Name", options=names, index=0, format_func=lambda x: x.lower())
    # # Button to fetch results
    # if st.button("Get results"):
    #     surname, first_name = name.split(", ")
    #     results = fetch_results(surname, first_name)
    #     # Display results in table
    #     if results:
    #         header = ["Event", "Year", "Race", "Position", "Sex Position",
    #                   "Category Position", "Surname", "Name", "Sex Category",
    #                   "Full Category", "Time"]
    #         st.subheader("Results:")
    #         st.table([header] + results)
    #     else:
    #         st.error("No results found for the provided name.")
    # else:
    #     st.warning("Please select a name.")


# Run the app
if __name__ == "__main__":
    main()
