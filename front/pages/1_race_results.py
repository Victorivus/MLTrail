'''
Viz test module for the Results class
'''
import os
import re
import traceback
import joblib
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sklearn.pipeline import Pipeline
from scraper.scraper import LiveTrailScraper
from results.results import Results
from ai.features import Features
from ai.xgboost import XGBoostRegressorModel
from database.models import Event
from database.create_db import Database


DATA_DIR_PATH = os.environ["DATA_DIR_PATH"]
DB_PATH = os.path.join(DATA_DIR_PATH, 'events.db')


# Initialize a LiveTrailScraper instance
scraper = LiveTrailScraper()


def get_results(event, year, race):
    '''
        Get results data function
    '''
    scraper.set_events([event])
    scraper.set_years([year])
    scraper.set_race(race)

    # Let's get the raw data about the race
    raw_results = scraper.get_data(race)
    race_info = scraper.get_race_info(bib_n=raw_results.iloc[0]['doss'])

    # Let's get the Control Points information
    control_points, _ = scraper.get_control_points()
    control_points = control_points[race]
    waves = True # some races have different departure times
    if '00' not in raw_results.columns:  # if results do not contain starting time
        waves = False
        control_points.pop(next(iter(control_points)))  # Remove 1st CP (starting line)

    raw_results.columns = list(raw_results.columns[:5]) + list(control_points.keys())
    raw_results = raw_results.sort_values(by=raw_results.columns[-1])
    times = raw_results[control_points.keys()]
    rs = Results(control_points=control_points, times=times, offset=race_info['hd'],
                 clean_days=False, start_day=int(race_info['jd']), waves=waves)

    return raw_results, control_points, rs, race_info, waves


def clean_events(events: dict) -> dict:
    '''
        Clean special characters, repeated names etc. from the events list
    '''
    # Remove years and strip
    events = {key: ' '.join(word for word in value.split() if not word.isdigit() or len(word) != 4).strip() for key, value in events.items()}
    events = {key: re.sub(r'^\d{4}|\d{4}$', '', value).strip() for key, value in events.items()}
    # Remove French ordinals
    events = {key: re.sub(r'(\d{1,2}(?:e|ème))', '', value).strip() for key, value in events.items()}
    # Remove HTML tags
    events = {key: re.sub(r'<[^<]+?>', '', value).strip() for key, value in events.items()}
    # Sort alphabetically
    events = dict(sorted(events.items(), key=lambda item: item[1]))

    return events


def main():
    '''
        Streamlit main function
    '''
    # Get the list of events and years
    events = scraper.get_events()
    years = scraper.get_events_years()

    # Get the list of events and years
    events = clean_events(dict(sorted(scraper.get_events().items(),
                                      key=lambda item: item[1])))

    event = st.selectbox('Select Event:', list(events.values()))
    event = next(key for key, value in events.items() if value == event)  # get key from value
    if event not in years:
        st.write(f'No data available for {events[event]}. Please select another event.')
    else:
        year = st.selectbox('Select Year:', years[event])
        # Get the races for the selected event and year
        scraper.set_events([event])
        scraper.set_years([year])
        races = scraper.get_races()
        if event not in races:
            st.write(f'No data available for {events[event]} {year}. Please select another event.')
        elif year not in races[event]:
            st.write(f'No data available for {events[event]} {year}. Please select another event or year.')
        else:
            races = races[event][year]

            race = st.selectbox('Select Race:', list(races.values()))
            race = next(key for key, value in races.items() if value == race)  # get key from value

            st.session_state.event = event
            st.session_state.year = year
            st.session_state.race = race

            st.title('Race Analysis')

            # Display analysis results
            if st.button('Generate Analysis'):
                folder_path = f'../data/plots/{event}'
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                file_path = os.path.join(folder_path, f'{event}_{race}_{year}.png')
                raw_results, control_points, rs, race_info, waves = get_results(event, year, race)
                rs.plot_control_points(rs.get_stats(), xrotate=True, inverty=True, save_path=file_path)
                data = {
                    'times': rs.get_hours().map(rs.format_time_over24h),
                    'hours': rs.get_hours().map(rs.format_hourtime_over24h),
                    'real_times': rs.get_real_times().map(rs.format_time_over24h),
                    'paces': rs.paces,
                    # 'plot_image_tag': file_path,
                    'event': event,
                    'year': year,
                    'race': race
                }
                st.session_state.race_info = race_info
                # Display data
                # TODO: Add button to toggle view between hours and time (apply or not rs.format_time_over24h)
                st.write(f"Departure time: {race_info['hd']}")
                st.write('Hours:')
                st.write(data['hours'].sort_index())

                st.write('Official Times:')
                st.write(data['real_times'].sort_index())
                if waves:
                    st.write('Real Times:')
                    st.write(data['real_times'].sort_index())

                st.write('Paces:')
                st.write(data['paces'].sort_index())

                st.image(file_path)

            input_time = st.text_input('Enter Objective Time (HH:MM:SS):')

            if st.button('Set Objective'):
                folder_path = f'../data/plots/{event}'
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                try:
                    event = st.session_state.event
                    year = st.session_state.year
                    race = st.session_state.race

                    raw_results, control_points, rs, race_info, waves = get_results(event, year, race)
                    objective_position = rs.get_closest_time_to_objective(input_time)

                    rs.set_objective(objective_position)
                    obj = rs.get_objective_paces()

                    mean_obj = rs.get_objective_mean_paces()
                    mean_obj_times = rs.get_objective_mean_times()

                    st.write('Total cumulative time per checkpoint:')
                    st.write(mean_obj_times)

                    index = ['objective', 'mean(obj)']
                    paces = pd.concat([obj, mean_obj], ignore_index=True)
                    paces['index'] = index
                    paces.set_index('index', inplace=True)

                    obj_file_path = os.path.join(folder_path, f'objective_{event}_{race}_{year}.png')
                    rs.plot_control_points(paces, xrotate=True, inverty=True, save_path=obj_file_path)

                    st.image(obj_file_path)

                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.error(traceback.format_exc())

            st.title('AI Time Predictions')
            if 'model_params' in st.session_state:
                if st.button('Generate AI powered predictions'):
                    if st.session_state.model_params is not None:        
                        with st.spinner('Loading race data...'):
                            event_id = Event.get_id_from_code_year(st.session_state.event, st.session_state.year, Database.create_database(DB_PATH))
                            metadata_features = [(event_id, st.session_state.race, "")]
                            feat = Features(metadata_features, DB_PATH)
                            data = feat.fetch_anonymous_features_table().drop(columns=['race_id', 'event_id'])
                        if len(data) == 0:
                            st.error("No data available for this race. Please choose another one.")
                        else:
                            with st.spinner('Loading the personalised AI model...'):
                                rgs = XGBoostRegressorModel(df=data, target_column=None, only_partials=False)
                                rgs.set_params(st.session_state['model_params'])
                                rgs.model = joblib.load(os.path.join(DATA_DIR_PATH, 'model.pkl'))
                                prediction = rgs.predict(data, format='time')
                                data['Prediction'] = prediction
                                results_cum = pd.concat([prediction,pd.Series([Features.get_seconds(x) for x in prediction.values],name='PRED CUMUL')],axis=1)
                                total_time = Features.format_time(float(results_cum.iloc[:-1]['PRED CUMUL'].values.sum()))
                                data.loc[data['dist_total'] == data['dist_segment'], 'Prediction'] = total_time
                            st.write(data.drop(columns=['dist_total', 'elevation_pos_total', 'elevation_neg_total']))
            else:
                st.write('Head to "my results" page to train an AI model on your data.')


if __name__ == '__main__':
    main()
