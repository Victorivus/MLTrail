import sys
import os
import csv
import sqlite3
from database.create_db import Database

# Function to connect to SQLite database
def connect_to_db(db_file):
    conn = sqlite3.connect(db_file)
    return conn

# Function to fetch race_id and event_id from races table
def fetch_race_event_ids(cursor, filepath):
    cursor.execute("SELECT race_id, event_id FROM races WHERE results_filepath=?", (filepath,))
    row = cursor.fetchone()
    if row:
        return row
    else:
        return None

# Function to insert data into results table
def insert_into_results(cursor, race_id, event_id, data):
    for row in data:
        cursor.execute("INSERT INTO results (race_id, event_id, position, bib, surname, name, full_category, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (race_id, event_id, *row,))  # Add a comma after *row        

def update_category(cursor):
    # Set category
    cursor.execute('''
                UPDATE results
                SET sex_category = 
                CASE 
                    WHEN LOWER(full_category) LIKE '%mx%' OR LOWER(full_category) LIKE '%mi%' THEN 'Mixed'
                    WHEN UPPER(full_category) LIKE '%H' OR UPPER(full_category) LIKE '%M' THEN 'Male'
                    WHEN UPPER(full_category) LIKE '%F' OR UPPER(full_category) LIKE '%D' OR UPPER(full_category) LIKE '%W' THEN 'Female'
                    ELSE NULL
                END;
                '''
                )

# Function to read CSV file
def read_csv(file_path):
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Skip header
        # CSV file header is
        # n, doss, nom, prenom, cat, {numbers for each control point of variable length}
        return [[row[0], row[1], row[2], row[3], row[4], row[-1]] for row in reader]

# Main function
def main(path='../data/parsed_data.db'):
    # Path to the directory containing folders of CSV files
    data_folder = '../../data/'

    db: Database = Database.create_database(path=path)

    # Connect to SQLite database
    db_connection = connect_to_db(db.path)
    cursor = db_connection.cursor()

    # Iterate through folders
    for folder in os.listdir(data_folder):
        folder_path = os.path.join(data_folder, folder)
        if os.path.isdir(folder_path):
            # Iterate through CSV files in the folder
            for file in os.listdir(folder_path):
                if file.endswith('.csv'):
                    file_path = os.path.join(folder_path, file)
                    # Fetch race_id and event_id from races table
                    race_event_ids = fetch_race_event_ids(cursor, f'data/{folder}/{file}')
                    if race_event_ids:
                        race_id, event_id = race_event_ids
                        # Read CSV file
                        csv_data = read_csv(file_path)
                        # Insert data into results table
                        insert_into_results(cursor, race_id, event_id, csv_data)

    # Commit changes and close connection
    db_connection.commit()
    
    cursor = db_connection.cursor()
    update_category(cursor)
    
    db_connection.commit()
    
    db_connection.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        path='../data/parsed_data.db'

    path = sys.argv[1]
    main(path)
