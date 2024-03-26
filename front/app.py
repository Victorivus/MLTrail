import os
import sys
import re
import random
import string
from datetime import timedelta
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, session
sys.path.append('../src/')
from results.results import Results
from scraper.scraper import Scraper
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Example: Session expires after 7 days

# Initialize a Scraper instance
scraper = Scraper()

# Define the route for the main page
@app.route('/')
def index():
    session['id'] = ''.join(random.choices(string.ascii_letters + string.digits, k=100))
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

    years = scraper.getEventsYears()
    
    # Pass the events to the template
    return render_template('index.html', events=events, years=years)

# Define an endpoint to get races
@app.route('/get_races', methods=['POST'])
def get_races():
    # Get the selected event and year from the request data
    event = request.json['event']
    year = request.json['year']

    # Set the event and year in the Scraper instance
    scraper.setEvents([event])
    scraper.setYears([year])

    # Get the races for the selected event and year
    races = scraper.getRaces()
    
    return jsonify(races)

@app.route('/analysis', methods=['POST'])
def generate_analysis():
    if request.is_json:
        event = request.json['event']
        year = request.json['year']
        race = request.json['race']
    else:
        event = request.form.get("events")
        year = request.form.get("year")
        race = request.form.get("race")

    raw_results, control_points, rs, race_info = getRS(event, year, race)

    folder_path = f'../data/plots/{event}'
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    file_path = os.path.join(folder_path,f'{event}_{race}_{year}.png')
    rs.plotControlPoints(rs.getStats(),xrotate=True,inverty=True, savePath=file_path)


    data = {
        'times': rs.times,
        'paces': rs.paces,
        'plot_image_tag': f'<img src="/plot/{event}_{race}_{year}.png" alt="Matplotlib Plot">',
        'event' : event,
        'year' : year,
        'race' : race
    }

    # Save for future request processing
    session['event'] = event
    session['year'] = year
    session['race'] = race
    session['race_info'] = race_info
    
    return render_template('analysis_template.html', data=data)

@app.route('/plot/<path:image_name>', methods=['GET'])
def get_plot(image_name):
    folder_path = f'../data/plots/{scraper.events[0]}'
    
    # Construct the full path to the image file based on the provided image name
    image_path = os.path.join(folder_path,image_name)
    print(f'image_path: {image_path}')
    # Use Flask's send_file function to send the image file in the response
    return send_file(image_path, mimetype='image/png')

@app.route('/plot/objective/<path:image_name>', methods=['GET'])
def get_objective_plot(image_name):
    folder_path = f'../data/plots/objective'
    
    # Construct the full path to the image file based on the provided image name
    image_path = os.path.join(folder_path,image_name)
    print(f'image_path: {image_path}')
    # Use Flask's send_file function to send the image file in the response
    return send_file(image_path, mimetype='image/png')

@app.route('/loadObjective', methods=['POST'])
def objective_form():
    # Get the objective position from the form data
    
    event = session['event']
    year = session['year']
    race = session['race']
    
    _, _, rs, _ = getRS(event, year, race)

    objective_time = request.form['objective']
    objective_position = rs.getClosestTimeToObjective(objective_time)
    rs.setObjective(objective_position)
    obj = rs.getObjectivePaces()
    mean_obj = rs.getObjectiveMeanPaces()
    index = ['objective','mean(obj)']
    paces = pd.concat([obj,mean_obj],ignore_index=True)
    paces['index'] = index
    paces.set_index('index',inplace=True)

    folder_path = f'../data/plots/objective'
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=100))
    file_path = os.path.join(folder_path,f'{random_string}.png')
    rs.plotControlPoints(paces, xrotate=True, inverty=True, savePath=file_path )

    return jsonify({'img_path': f'/plot/objective/{random_string}.png'})

def getRS(event, year, race):
    
    scraper.setEvents([event])
    scraper.setYears([year])
    scraper.setRace(race)
    
    # Let's get the raw data about the race
    raw_results = scraper.getData(race)
    race_info = scraper.getRaceInfo(bibN=raw_results.iloc[0]['doss'])
    
    # Let's get the Control Points information
    control_points = scraper.getControlPoints()[race]
    control_points.pop(next(iter(control_points))) # Remove 1st CP (starting line)

    raw_results.columns = list(raw_results.columns[:5]) + [k for k in control_points.keys()]
    
    times = raw_results[control_points.keys()]
    rs = Results(controlPoints=control_points, times=times, offset=race_info['hd'], cleanDays=False)

    return raw_results, control_points, rs, race_info

if __name__ == '__main__':
    # Run the Flask app
    app.run(debug=True)