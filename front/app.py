import os
import sys
import re
import traceback
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.scraper.scraper import Scraper
from src.results.results import Results

# Load variables from .env file
load_dotenv()


# Function to store session-like data using Streamlit's caching mechanism
@st.cache_data(hash_funcs={dict: lambda _: None})
def get_session_data():
    return {}


# Initialize a Scraper instance
scraper = Scraper()


def getRS(event, year, race):
    scraper.setEvents([event])
    scraper.setYears([year])
    scraper.setRace(race)

    # Let's get the raw data about the race
    raw_results = scraper.getData(race)
    race_info = scraper.getRaceInfo(bibN=raw_results.iloc[0]['doss'])

    # Let's get the Control Points information
    control_points = scraper.getControlPoints()[race]
    control_points.pop(next(iter(control_points)))  # Remove 1st CP (starting line)

    raw_results.columns = list(raw_results.columns[:5]) + [k for k in control_points.keys()]
    raw_results = raw_results.sort_values(by=raw_results.columns[-1])
    times = raw_results[control_points.keys()]
    rs = Results(controlPoints=control_points, times=times, offset=race_info['hd'],
                 cleanDays=False, startDay=int(race_info['jd']))

    return raw_results, control_points, rs, race_info


def main():
    # Get the list of events and years
    events = scraper.getEvents()
    years = scraper.getEventsYears()

    # Get the list of events and years
    events = dict(sorted(scraper.getEvents().items(), key=lambda item: item[1]))
    # Remove years and strip
    events = {key: ' '.join(word for word in value.split() if not word.isdigit() or len(word) != 4).strip() for key, value in events.items()}
    events = {key: re.sub(r'^\d{4}|\d{4}$', '', value).strip() for key, value in events.items()}
    # Remove French ordinals
    events = {key: re.sub(r'(\d{1,2}(?:e|ème))', '', value).strip() for key, value in events.items()}
    # Remove HTML tags
    events = {key: re.sub(r'<[^<]+?>', '', value).strip() for key, value in events.items()}
    # Sort alphabetically
    events = dict(sorted(events.items(), key=lambda item: item[1]))

    event = st.selectbox('Select Event:', list(events.values()))
    event = next(key for key, value in events.items() if value == event)  # get key from value
    year = st.selectbox('Select Year:', years[event])

    # Get the races for the selected event and year
    scraper.setEvents([event])
    scraper.setYears([year])
    races = scraper.getRaces()[event][year]

    race = st.selectbox('Select Race:', list(races.values()))
    race = next(key for key, value in races.items() if value == race)  # get key from value

    # Retrieve or initialize session-like data
    session_data = get_session_data()

    session_data['event'] = event
    session_data['year'] = year
    session_data['race'] = race
    # session_data['race_info'] = race_info

    # # Display session-like data
    # st.write('Session Data:')
    # st.write(session_data)

    st.title('Race Analysis')

    # Display analysis results
    if st.button('Generate Analysis'):
        folder_path = f'../data/plots/{event}'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        file_path = os.path.join(folder_path, f'{event}_{race}_{year}.png')
        raw_results, control_points, rs, race_info = getRS(event, year, race)
        rs.plotControlPoints(rs.getStats(), xrotate=True, inverty=True, savePath=file_path)
        data = {
            'times': rs.times.map(rs.formatTimeOver24h),
            'paces': rs.paces,
            # 'plot_image_tag': file_path,
            'event': event,
            'year': year,
            'race': race
        }
        # Display data
        # TODO: Add button to toggle view between hours and time (apply or not rs.formatTimeOver24h)
        st.write(f"Departure time: {race_info['hd']}")
        st.write('Times:')
        st.write(data['times'])

        st.write('Paces:')
        st.write(data['paces'])

        st.image(file_path)
        
    input_time = st.text_input('Enter Objective Time (HH:MM:SS):')
                
    if st.button('Set Objective'):
        folder_path = f'../data/plots/{event}'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        st.write(input_time)
        try:
            event = session_data['event']
            year = session_data['year']
            race = session_data['race']
            st.write(event, year, race)
            raw_results, control_points, rs, race_info = getRS(event, year, race)
            objective_position = rs.getClosestTimeToObjective(input_time)

            rs.setObjective(objective_position)
            obj = rs.getObjectivePaces()

            mean_obj = rs.getObjectiveMeanPaces()
            mean_obj_times = rs.getObjectiveMeanTimes()

            st.write('Times:')
            st.write(mean_obj_times)

            index = ['objective', 'mean(obj)']
            paces = pd.concat([obj, mean_obj], ignore_index=True)
            paces['index'] = index
            paces.set_index('index', inplace=True)

            obj_file_path = os.path.join(folder_path, f'objective_{event}_{race}_{year}.png')
            rs.plotControlPoints(paces, xrotate=True, inverty=True, savePath=obj_file_path)

            st.image(obj_file_path)

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.error(traceback.format_exc())


if __name__ == '__main__':
    main()
