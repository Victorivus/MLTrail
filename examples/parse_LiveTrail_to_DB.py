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


def parse_done_txt_file(file_path) -> dict:
    '''Used to resume from a partial download'''
    with open(file_path, 'r', encoding='utf-8') as file:
        parsed_data = {}
        for line in file:
            parts = line.strip().split()
            if len(parts) == 2:
                race_name = parts[0]
                years = [year for year in parts[1:]]
                parsed_data.setdefault(race_name, []).extend(years)
    return parsed_data


def main(path='../data/parsed_data.db', clean=False, update=False):
    '''Script used to parse LiveTrail and insert all available data into DB.'''   
    db: Database = Database.create_database(path=path)

    scraper = LiveTrailScraper()
    events = scraper.get_events()
    years = scraper.get_events_years()

    # Get the list of events and years
    events = dict(sorted(scraper.get_events().items(), key=lambda item: item[1]))
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

    parsed_races = parse_done_txt_file('output_parsing.txt')
    for event, name in events.items():
        if event in years:
            for year in years[event]:
                if event in parsed_races:
                    if year in parsed_races[event]:
                        continue
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
                        if race=='maxirace' and 'Orientation' in name:
                            # 'maxirace' has two orientation races not standard
                            continue
                        elif name.lower()=='course des partenaires':
                            continue
                        scraper.set_race(race)
                        folder_path = f'data/{event}'
                        filepath = os.path.join(folder_path, f'{event}_{race}_{year}.csv')
                        results_filepath = filepath if os.path.exists(os.path.join('../../',filepath)) else None
                        race_info = scraper.get_race_info(bibN=rr[year][race]) if rr[year][race] is not None else {'date':None, 'hd':None}
                        control_points = cps[race]
                        race_data = races_data[race]
                        if race_info: # some races are empty but have empty rows in data (e.g. 'templiers', 'Templi', 2019)
                            # the .split('.')[0] is needed since few races sometime contain a dot at the end or '000' for milliseconds
                            departure_datetime = ' '.join([race_info['date'], race_info['hd']]).split('.')[0] if race_info['date'] else None
                        else:
                            departure_datetime = None
                        r = Race(race_id=race, event_id=event_id, race_name=name, distance=race_data['distance'],
                        elevation_pos=race_data['elevation_pos'], elevation_neg=race_data['elevation_pos'], departure_datetime=departure_datetime,
                        results_filepath=results_filepath, db=db)
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
                                                (event_id, race, cp_code, cpns[race][cp_code], # Name not scraped
                                                    data[0], data[1], data[2],))
                                except sqlite3.IntegrityError:
                                    pass
    for script in ['CSV_to_DB_results', 'CSV_to_DB_timing_points']:
        command = f"python {script}.py -p ../data/parsed_data.db"
        if clean:
            command += " -c"
        os.system(command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Data loader from CSV files into results table.')
    parser.add_argument('-p', '--path', default='../data/parsed_data.db', help='DB path.')
    parser.add_argument('-c', '--clean', action='store_true', help='Remove all data from table before execution.')
    parser.add_argument('-u', '--update', action='store_true', help='Download only events and reces not already present in DB.')

    args = parser.parse_args()
    path = args.path
    clean = args.clean
    update = args.update

    main(path=path, clean=clean, update=update)
