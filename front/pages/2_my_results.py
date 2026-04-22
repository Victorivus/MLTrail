"""Personal Results and AI Model Training page.

Two-stage flow:
  1. Search → user picks which rows are actually theirs (handles spelling
     variants and namesakes) and adds them to ``user_results``.
  2. My Results table → persistent per-user list. The ``Train`` checkbox
     soft-deletes a row from training without removing it.
"""
import time
import logging
import sqlite3
import streamlit as st
import pandas as pd
from config import get_config
from auth import require_auth
from database.create_db import Database
from ai.training_service import TrainingState, TrainingStatus, start_background_training

logger = logging.getLogger(__name__)

cfg = get_config()
DATA_DIR_PATH = cfg.data_dir_path
DB_PATH = cfg.db_path

if not require_auth(DB_PATH):
    st.stop()

# Backfill the user_results table for databases that predate this feature.
Database.ensure_user_results_table(DB_PATH)


SEARCH_COLUMNS = [
    "event_id", "race_id", "bib",
    "Event", "Year", "Race",
    "Position", "Sex Position", "Category Position",
    "Surname", "Name", "Sex Category", "Full Category", "Time",
]
MY_RESULTS_COLUMNS = ["Train"] + SEARCH_COLUMNS


def fetch_results(surname, first_name=None):
    '''
    Search the shared results table by surname (or "surname, name").
    '''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    base_query = """
        SELECT results.event_id, results.race_id, results.bib,
               events.name, events.year, races.race_name,
               results.position, results.cat_position, results.full_cat_position,
               results.surname, results.name,
               results.sex_category, results.full_category, results.time
        FROM results
        INNER JOIN events ON events.event_id = results.event_id
        INNER JOIN races ON races.race_id = results.race_id
                         AND races.event_id = results.event_id
    """
    if first_name is None and ',' not in surname:
        cursor.execute(base_query + " WHERE LOWER(results.surname) LIKE ?",
                       ('%' + surname.lower() + '%',))
    else:
        if ',' in surname:
            surname, first_name = [part.strip() for part in surname.split(",")]
        cursor.execute(
            base_query + " WHERE LOWER(results.surname) LIKE ? AND LOWER(results.name) LIKE ?",
            (surname.lower(), first_name.lower()),
        )

    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_my_results(user_id):
    '''
    Fetch this user's saved results joined with event/race metadata.
    '''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ur.include_in_training,
               ur.event_id, ur.race_id, ur.bib,
               events.name, events.year, races.race_name,
               results.position, results.cat_position, results.full_cat_position,
               results.surname, results.name,
               results.sex_category, results.full_category, results.time
        FROM user_results ur
        INNER JOIN results ON results.event_id = ur.event_id
                           AND results.race_id  = ur.race_id
                           AND results.bib      = ur.bib
        INNER JOIN events  ON events.event_id   = ur.event_id
        INNER JOIN races   ON races.race_id     = ur.race_id
                           AND races.event_id   = ur.event_id
        WHERE ur.user_id = ?
        ORDER BY events.year DESC, events.name
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def add_to_my_results(user_id, keys):
    '''
    Insert (user_id, event_id, race_id, bib) tuples. Duplicates are ignored.
    '''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT OR IGNORE INTO user_results (user_id, event_id, race_id, bib)
        VALUES (?, ?, ?, ?)
        """,
        [(user_id, int(event_id), race_id, bib) for event_id, race_id, bib in keys],
    )
    inserted = conn.total_changes
    conn.commit()
    conn.close()
    return inserted


def update_training_flags(user_id, flag_by_key):
    '''
    flag_by_key: dict[(event_id, race_id, bib)] -> bool
    '''
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany(
        """
        UPDATE user_results SET include_in_training = ?
        WHERE user_id = ? AND event_id = ? AND race_id = ? AND bib = ?
        """,
        [(int(flag), user_id, int(event_id), race_id, bib)
         for (event_id, race_id, bib), flag in flag_by_key.items()],
    )
    conn.commit()
    conn.close()


def _init_session_state():
    st.session_state.setdefault('search_results_df', None)
    st.session_state.setdefault('model_params', None)
    st.session_state.setdefault('ai_trained_button_clicked', False)
    st.session_state.setdefault('training_state', TrainingState())


def _render_search_section(user_id):
    st.header("Search for your results")
    st.caption(
        "Search by `surname` or `surname, name`. You can run several searches "
        "with different spellings and add the matching rows to *My Results*."
    )

    surname = st.text_input("Surname (or `surname, name`):", key="search_input")

    if st.button("Search"):
        if not surname:
            st.warning("Please enter a surname.")
        else:
            with st.spinner("Searching..."):
                rows = fetch_results(surname)
            if not rows:
                st.warning("No results found for that query.")
                st.session_state.search_results_df = None
            else:
                df = pd.DataFrame(rows, columns=SEARCH_COLUMNS)
                df.insert(0, "Mine", False)
                st.session_state.search_results_df = df

    df = st.session_state.search_results_df
    if df is None:
        return

    st.markdown("Tick the rows that are **yours**, then click *Add selected*.")
    edited = st.data_editor(
        df,
        key="search_editor",
        hide_index=True,
        use_container_width=True,
        column_config={
            "Mine": st.column_config.CheckboxColumn(required=True),
            "event_id": None,
            "race_id": None,
            "bib": None,
        },
        disabled=[c for c in df.columns if c != "Mine"],
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Add selected"):
            selected = edited[edited["Mine"].astype(bool)]
            if selected.empty:
                st.warning("No rows selected.")
            else:
                keys = [
                    (r.event_id, r.race_id, r.bib)
                    for r in selected.itertuples(index=False)
                ]
                add_to_my_results(user_id, keys)
                st.success(f"Added {len(keys)} result(s) to My Results.")
                st.session_state.search_results_df = None
                # Reset editor widget state so the next search starts clean.
                st.session_state.pop("search_editor", None)
                st.rerun()
    with col2:
        if st.button("Clear search"):
            st.session_state.search_results_df = None
            st.session_state.pop("search_editor", None)
            st.rerun()


def _render_my_results_section(user_id):
    '''
    Returns the list of (event_id, race_id, bib) tuples flagged for training.
    '''
    st.header("My Results")
    rows = fetch_my_results(user_id)
    if not rows:
        st.info("No saved results yet. Use the search above to add some.")
        return []

    df = pd.DataFrame(rows, columns=MY_RESULTS_COLUMNS)
    df["Train"] = df["Train"].astype(bool)

    st.caption(
        "Uncheck **Train** to keep a row but exclude it from model training. "
        "Unchecked rows still live here — re-check to include them again."
    )

    edited = st.data_editor(
        df,
        key="my_results_editor",
        hide_index=True,
        use_container_width=True,
        column_config={
            "Train": st.column_config.CheckboxColumn(default=True),
            "event_id": None,
            "race_id": None,
            "bib": None,
        },
        disabled=[c for c in df.columns if c != "Train"],
    )

    # Persist any Train-flag changes the user made this run.
    changes = {}
    for orig, new in zip(df.itertuples(index=False), edited.itertuples(index=False)):
        if bool(orig.Train) != bool(new.Train):
            changes[(orig.event_id, orig.race_id, orig.bib)] = bool(new.Train)
    if changes:
        update_training_flags(user_id, changes)

    training_rows = edited[edited["Train"].astype(bool)]
    st.caption(f"**{len(training_rows)} of {len(edited)}** results will be used for training.")
    return [
        (int(r.event_id), r.race_id, r.bib)
        for r in training_rows.itertuples(index=False)
    ]


def _render_training_section(training_metadata):
    st.header("AI Model Training")
    training_state = st.session_state.training_state

    # Already trained → show status + reset option.
    if st.session_state.model_params is not None:
        st.success(
            "Model trained! Head to **Race Results** to predict racing times. "
            "Retrain at any time to include new additions or selection changes."
        )
        if st.button("Reset model"):
            st.session_state.model_params = None
            st.session_state.ai_trained_button_clicked = False
            st.session_state.training_state = TrainingState()
            st.rerun()

    if training_state.is_running:
        st.info(f"**{training_state.progress_message}**")
        elapsed = training_state.elapsed_seconds
        st.progress(min(elapsed / 120.0, 0.99), text=f"Elapsed: {elapsed:.0f}s")
        time.sleep(2)
        st.rerun()
        return

    if training_state.status == TrainingStatus.COMPLETED:
        st.success(training_state.progress_message)
        st.session_state.model_params = training_state.model_params
        st.session_state.ai_trained_button_clicked = True
        st.session_state.training_state = TrainingState()
        st.rerun()
        return

    if training_state.status == TrainingStatus.FAILED:
        st.error(f"Training failed: {training_state.error_message}")
        st.session_state.training_state = TrainingState()

    if not training_metadata:
        st.warning("Select at least one result in *My Results* to enable training.")
        return

    label = "Retrain AI model" if st.session_state.model_params is not None else "Train AI model"
    if st.button(label):
        start_background_training(
            state=training_state,
            metadata_features=training_metadata,
            db_path=DB_PATH,
            model_save_path=cfg.model_path,
        )
        st.rerun()


def main():
    '''
    Main function for the Streamlit page
    '''
    st.set_page_config(layout="wide")
    st.title("My Results & AI Model Training")
    st.markdown("*Scraped from LiveTrail up to 04/08/2024.*")

    user_id = st.session_state.get('user_id')
    if user_id is None:
        st.error("You must be logged in.")
        return

    _init_session_state()

    _render_search_section(user_id)
    st.divider()
    training_metadata = _render_my_results_section(user_id)
    st.divider()
    _render_training_section(training_metadata)


if __name__ == "__main__":
    main()
