#!/usr/bin/env python
# coding: utf-8

import os
import re
import sys
import argparse
import sqlite3
from scraper.scraper import LiveTrailScraper
from database.create_db import Database
from database.database import Event, Race
from database.loader_LiveTrail import CSV_to_DB_results, CSV_to_DB_timing_points
import warnings
from bs4 import GuessedAtParserWarning


# Suppress the XMLParsedAsHTMLWarning
warnings.filterwarnings('ignore', category=GuessedAtParserWarning)
warnings.filterwarnings("ignore", message=".*XMLParsedAsHTMLWarning.*")


def parse_events_years_txt_file(file_path) -> dict:
    '''Used to resume from a partial download'''
    with open(file_path, 'r', encoding='utf-8') as file:
        parsed_data = {}
        for line in file:
            parts = line.strip().split()
            if len(parts) == 2:
                race_name = parts[0]
                years = list(parts[1:])
                parsed_data.setdefault(race_name, []).extend(years)
    return parsed_data


def save_years_to_txt(filename, years):
    """
    Saves the events and years to a text file, formatted as 'code year', one per line.

    Args:
        filename (str): The name of the file to save the years.
        years (dict): A dictionary containing the years for each event code.
    """
    with open(filename, 'w', encoding='utf-8') as file:
        for code, yrs in years.items():
            for year in yrs:
                file.write(f"{code} {year}\n")


def get_years_only_in_v1(events, years_v1, years_v2) -> tuple[dict, dict]:
    """
    Compares two versions of the 'years' dictionaries and returns the years that are only in years_v1.

    Args:
        events (dict): Dictionary where keys and values are event codes and event names respectively.
        years_v1 (dict): First version of the years dictionary where keys are event codes and values are lists of years.
        years_v2 (dict): Second version of the years dictionary where keys are event codes and values are lists of years.

    Returns:
        dict: A dictionary containing the years that are only in years_v1 for each event code.
              Format: {event_code: [years_only_in_v1] }
    """
    only_in_v1 = {}

    for key in events.keys():
        if key in years_v1:
            # Convert lists to sets for comparison
            set_v1 = set(years_v1.get(key, []))
            set_v2 = set(years_v2.get(key, []))

            # Find years only in v1
            diff_v1 = list(set_v1 - set_v2)

            if diff_v1:
                only_in_v1[key] = diff_v1

    # Drop keys from events not present in only_in_v1
    filtered_events = {k: v for k, v in events.items() if k in only_in_v1}

    return filtered_events, only_in_v1

def generate_code_year_txt(db_path, output_file: str = None) -> dict:
    '''
    Get all axisting events in the Database.

    Args:
        db_path (str): The path to the SQLite database file.
        output_file (str): The path to the output text file where the results will be saved if specified.

    Returns:
        None
    '''
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query the events table to get code and year
    cursor.execute("SELECT code, year FROM events;")
    rows = cursor.fetchall()
    parsed_years = {}
    for row in rows:
        race_name = row[0]
        years = [year for year in row[1:]]
        parsed_years.setdefault(race_name, []).extend(years)

    if output_file:
        # Open the output file in write mode
        with open(output_file, 'w', encoding='utf-8') as file:
            for row in rows:
                # Write each code and year separated by a space
                file.write(f"{row[0]} {row[1]}\n")

    # Close the database connection
    conn.close()
    return parsed_years

def main(path='../data/parsed_data.db', clean=False, update=False):
    '''Script used to parse LiveTrail and insert all available data into DB.'''   
    db: Database = Database.create_database(path=path)

    scraper = LiveTrailScraper()
    events = scraper.get_events()
    years = scraper.get_events_years()

    _, db_years = Event.get_events_years(db)

    if update:
        generate_code_year_txt(db.path, output_file='update.txt')
        events, years = get_years_only_in_v1(events, years, db_years)
    # Get the list of events and years
    events = dict(sorted(events.items(), key=lambda item: item[1]))
    # Remove years and strip
    events = {key: ' '.join(word for word in value.split() if not word.isdigit() or len(word) != 4).strip() for key, value in events.items()}
    events = {key: re.sub(r'^\d{4}|\d{4}$', '', value).strip() for key, value in events.items()}
    # Remove French ordinals
    events = {key: re.sub(r'(\d{1,2}(?:e|ème))', '', value).strip() for key, value in events.items()}
    # Remove HTML tags
    events = {key: re.sub(r'<[^<]+?>', '', value).strip() for key, value in events.items()}
    # Sort alphabetically
    events = dict(sorted(events.items(), key=lambda item: item[1]))

    for code, name in events.items():
        if code in years:
            for year in years[code]: 
                event = Event(event_code=code,
                              event_name=name,
                              year=year,
                              country=None,
                              db=db)
                event.save_to_database()


# If you want to skip races, create a text file `output_parsing.txt` containing one code and year per line wanting to be ignored, for example:
# 
# ```
# saintelyon 2018
# saintelyon 2017
# saintelyon 2016
# saintelyon 2015
# saintelyon 2014
# saintelyon 2013
# penyagolosa 2024
# penyagolosa 2023
# penyagolosa 2022
# penyagolosa 2021
# penyagolosa 2019
# # lut 2016 -> parcours.php is empty
# lut 2016
# # oxfamtrailwalkerhk 2021 -> Password protected
# oxfamtrailwalkerhk 2021
# ```

    #  parsed_races = parse_events_years_txt_file('output_parsing.txt')
    for event, name in events.items():
        if event in years:
            for year in years[event]:
                # if event in parsed_races:
                #     if year in parsed_races[event]:
                #         continue
                print(event, year)
                scraper.set_events([event])
                scraper.set_years([year])
                cps, cpns = scraper.get_control_points()
                event_id = Event.get_id_from_code_year(event, year, db=db)
                if not cps:
                    continue
                races = scraper.get_races()
                rr = scraper.get_random_runner_bib()
                scraper.download_data()
                races_data = scraper.get_races_physical_details()
                if event not in races:
                    #st.write(f'No data available for {events[event]} {year}. Please select another event.')
                    pass
                elif year not in races[event]:
                    #st.write(f'No data available for {events[event]} {year}. Please select another event or year.')
                    pass
                else:
                    races = races[event][year]
                    for race, name in races.items():
                        if race not in cps:
                            continue
                        if race == 'maxirace' and 'Orientation' in name:
                            # 'maxirace' has two orientation races not standard
                            continue
                        elif name.lower() == 'course des partenaires':
                            continue
                        scraper.set_race(race)
                        folder_path = f'data/{event}'
                        filepath = os.path.join(folder_path, f'{event}_{race}_{year}.csv')
                        results_filepath = filepath if os.path.exists(os.path.join('../../',filepath)) else None
                        race_info = scraper.get_race_info(bibN=rr[year][race]) if rr[year][race] is not None else {'date':None, 'hd':None}
                        control_points = cps[race]
                        race_data = races_data[race]
                        if race_info:  # some races are empty but have empty rows in data (e.g. 'templiers', 'Templi', 2019)
                            # the .split('.')[0] is needed since few races sometime contain a dot at the end or '000' for milliseconds
                            departure_datetime = ' '.join([race_info['date'], race_info['hd']]).split('.')[0] if race_info['date'] else None
                        else:
                            departure_datetime = None
                        r = Race(race_id=race, event_id=event_id, race_name=name, distance=race_data['distance'],
                                 elevation_pos=race_data['elevation_pos'], elevation_neg=race_data['elevation_pos'],
                                 departure_datetime=departure_datetime, results_filepath=results_filepath, db=db)
                        r.save_to_database()
                        for cp_code, data in cps[race].items():
                            conn = sqlite3.connect(db.path, timeout=3600)
                            with conn:
                                cursor = conn.cursor()
                                try:
                                    cursor.execute('''
                                                INSERT INTO control_points
                                                            (event_id, race_id, code, name,
                                                            distance, elevation_pos, elevation_neg)
                                                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                                   (event_id, race, cp_code, cpns[race][cp_code],  # Name not scraped
                                                    data[0], data[1], data[2],))
                                except sqlite3.IntegrityError:
                                    pass
                    break  # TODO: DEBUG
                break  # TODO: DEBUG
            break  # TODO: DEBUG
    for script in [CSV_to_DB_results, CSV_to_DB_timing_points]:
        actual_path = os.getcwd()  # os.path.split(os.path.realpath(__file__))
        if update:
            script.main(path=os.path.join(actual_path, path), clean=clean,
                        update=os.path.join(actual_path, "update.txt"))
        else:
            script.main(path=os.path.join(actual_path, path), clean=clean)
    print("INFO: Updated events:")
    print(open('updated_events_years.txt').read())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Data loader from CSV files into results table.')
    parser.add_argument('-p', '--path', default='../data/parsed_data.db', help='DB path.')
    parser.add_argument('-d', '--data-path', default='../../data/', help='CSV files path.')
    parser.add_argument('-c', '--clean', action='store_true', help='Remove all data from table before execution.')
    parser.add_argument('-u', '--update', action='store_true', help='Download only events and reces not already present in DB.')

    args = parser.parse_args()
    path = args.path
    clean = args.clean
    update = args.update

    main(path=path, clean=clean, update=update)
