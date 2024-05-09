import sys
import os
import csv
import sqlite3
import argparse
from datetime import datetime, timedelta
from database.create_db import Database

# Function to connect to SQLite database
def connect_to_db(db_file):
    conn = sqlite3.connect(db_file, timeout=3600)
    return conn

# Function to fetch race_id and event_id from races table
def fetch_race_event_ids(cursor, filepath):
    cursor.execute("SELECT race_id, event_id FROM races WHERE results_filepath=?", (filepath,))
    row = cursor.fetchone()
    if row:
        return row
    else:
        return None
# Function to fetch race_id and event_id from races table
def fetch_all_event_ids(cursor):
    cursor.execute("SELECT DISTINCT(event_id) FROM races WHERE results_filepath IS NOT NULL AND results_filepath NOT LIKE ''")
    event_ids = []
    for row in cursor.fetchall():
        event_ids.append(row[0])
    return event_ids

# Function to fetch race's departure date_time
def fetch_departure_date_time(cursor, race_id, event_id) -> datetime | None:
    # Fetch departure time from races table
    cursor.execute("SELECT departure_datetime FROM races WHERE race_id = ? AND event_id = ?", (race_id, event_id))
    row = cursor.fetchone()
    if row:
        if row[0] is not None:
            departure_time = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            return departure_time
    return None

# Function to insert data into results table
def insert_into_results(cursor, race_id, event_id, departure_time, data):
    
    if departure_time is not None:
        previous_time = departure_time # to take into account >24h races
        for row in data:
            # Parse the time from the row
            time_str = row[-1]
            if time_str != '' and time_str is not None:
                time = datetime.strptime(time_str, '%H:%M:%S')
                time = time.replace(year=departure_time.year, month=departure_time.month, day=departure_time.day)
                #time_difference = str((time - departure_time).total_seconds())
                time_difference = calculate_time_difference(time, previous_time)
                time = previous_time + time_difference
                time_str = format_timedelta(calculate_time_difference(time,departure_time))
                previous_time = time
            cursor.execute("INSERT INTO results (race_id, event_id, position, bib, surname, name, full_category, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (race_id, event_id, *row[:5], time_str,))
    else:
        for row in data:
            cursor.execute("INSERT INTO results (race_id, event_id, position, bib, surname, name, full_category, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (race_id, event_id, *row,))

# Function to calculate time difference and handle cases where it exceeds 24 hours
def calculate_time_difference(time, previous_time):
    # Check if the time is before the previous time
    if time < previous_time:
        # Add 24 hours to the time difference
        time = time + timedelta(days=1)
        return calculate_time_difference(time, previous_time)
    else:
        # Calculate the time difference
        return time - previous_time

# Function to format timedelta as HH:MM:SS
def format_timedelta(td):
    # Extract days, hours, minutes, and seconds
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    # Format as HH:MM:SS
    return f"{days * 24 + hours:02d}:{minutes:02d}:{seconds:02d}"

def update_category(cursor, event_id):
    # Set category
    cursor.execute('''
                    UPDATE results
                    SET sex_category = 
                    CASE 
                        WHEN LOWER(full_category) LIKE '%mx%' OR LOWER(full_category) LIKE '%mi%' THEN 'Mixed'
                        WHEN UPPER(full_category) LIKE '%H' OR UPPER(full_category) LIKE '%M' THEN 'Male'
                        WHEN UPPER(full_category) LIKE '%F' OR UPPER(full_category) LIKE '%D' OR UPPER(full_category) LIKE '%W' THEN 'Female'
                        ELSE NULL
                    END
                    WHERE event_id = ?
                    ''', (event_id,)
                   )

def compute_category_rankings(cursor, event_id):
    # Set category
    cursor.execute('''
                    WITH RankedResults AS (
                    SELECT 
                        race_id, 
                        event_id, 
                        bib, 
                        surname, 
                        name, 
                        full_category, 
                        sex_category,
                        time,
                        RANK() OVER (PARTITION BY race_id, event_id, sex_category ORDER BY TIME(time)) AS cat_position_rank,
                        RANK() OVER (PARTITION BY race_id, event_id, full_category ORDER BY TIME(time)) AS full_cat_position_rank
                    FROM
                        results
                    WHERE
                        full_category NOT LIKE '' AND full_category IS NOT NULL
                        AND time NOT LIKE '' AND time IS NOT NULL
                        AND event_id=?
                )
                UPDATE results
                SET 
                    cat_position = cat_position_rank,
                    full_cat_position = full_cat_position_rank
                FROM 
                    RankedResults
                WHERE 
                    results.race_id = RankedResults.race_id
                    AND results.event_id = RankedResults.event_id
                    AND results.bib = RankedResults.bib
                    AND results.event_id=?
                    ''', (event_id, event_id,)
                   )

# Function to read CSV file
def read_csv(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        # CSV file header is
        # n, doss, nom, prenom, cat, {numbers for each control point of variable length}
        return [[row[0], row[1], row[2], row[3], row[4], row[-1]] for row in reader]

def clean_table(cursor):
    cursor.execute('''
        DELETE 
        FROM results
    ''')

# Main function
def main(path='../data/parsed_data.db', clean=False):
    # Path to the directory containing folders of CSV files
    data_folder = '../../data/'

    db: Database = Database.create_database(path=path)

    if clean:
        db_connection = connect_to_db(db.path)
        with db_connection:
            cursor = db_connection.cursor()
            clean_table(cursor)
            print('Results table emptied')

    # Iterate through folders
    for folder in os.listdir(data_folder):
        folder_path = os.path.join(data_folder, folder)
        if os.path.isdir(folder_path):
            # Iterate through CSV files in the folder
            for file in os.listdir(folder_path):
                if file.endswith('.csv'):
                    file_path = os.path.join(folder_path, file)
                    # Fetch race_id and event_id from races table

                    db_connection = connect_to_db(db.path)
                    with db_connection:
                        cursor = db_connection.cursor()
                        race_event_ids = fetch_race_event_ids(cursor, f'data/{folder}/{file}')
                        if race_event_ids:
                            race_id, event_id = race_event_ids
                            print(f'Inserting data into {event_id}. {folder}, {race_id}')
                            departure_time = fetch_departure_date_time(cursor, race_id, event_id)
                            # Read CSV file
                            csv_data = read_csv(file_path)
                            # Insert data into results table
                            insert_into_results(cursor, race_id, event_id, departure_time, csv_data)
                            update_category(cursor, event_id)
                        db_connection.commit()
                    db_connection.close()

    db_connection = connect_to_db(db.path)
    with db_connection:
        cursor = db_connection.cursor()
        event_ids = fetch_all_event_ids(cursor)

    for event_id in event_ids:
        with db_connection:
            cursor = db_connection.cursor()
            compute_category_rankings(cursor, event_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Data loader from CSV files into results table.')
    parser.add_argument('-p', '--path', default='../data/parsed_data.db', help='DB path.')
    parser.add_argument('-c', '--clean', action='store_true', help='Remove all data from table before execution.')

    args = parser.parse_args()
    path = args.path
    clean = args.clean

    main(path=path, clean=clean)
