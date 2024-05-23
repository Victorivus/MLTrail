# ML Trail Library

Work in progress.

Lib to process results, make analysis of Trail running races and eventually build models to predict performances.

# Installation

Install Poetry:

**Linux, macOS, Windows (WSL)**
```
curl -sSL https://install.python-poetry.org | python3 -
```
**Windows (Powershell)**
```
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```
> If you have installed Python through the Microsoft Store, replace py with python in the command above.

(More details, methods or problem solving on [Poetry Installation Page](https://python-poetry.org/docs/#installation).)

Execute the following command:

```
poetry install
```

# Download data from LiveTrail locally 
Launch the following command:

```
python src/database/loader_LiveTrail/db_LiveTrail_loader.py -p data/parsed_data.db -d ../data
```

usage: db_LiveTrail_loader.py [-h] [-p PATH] [-d DATA_PATH] [-c] [-u]

Data loader from LiveTrail website into DB.

```bash
options:
  -h, --help            show this help message and exit
  -p PATH, --path PATH  DB path.
  -d DATA_PATH, --data-path DATA_PATH
                        CSV files path.
  -c, --clean           Remove all data from tables before execution.
  -u, --update          Download only events and reces not already present in DB.
```

If you want to skip races, create a text file `parsed_races.txt` containing one code and year per line wanting to be ignored, for example:

```
saintelyon 2018
saintelyon 2017
saintelyon 2016
saintelyon 2015
saintelyon 2014
saintelyon 2013
penyagolosa 2024
penyagolosa 2023
penyagolosa 2022
penyagolosa 2021
penyagolosa 2019
# lut 2016 -> parcours.php is empty
lut 2016
# oxfamtrailwalkerhk 2021 -> Password protected
oxfamtrailwalkerhk 2021
```

# Launch web app
Launch the following command:

```
streamlit run front/MLTrail.py
```

# Collaborating

## TO-DO list
- [X] Automatically parse LiveTrail data.
- [X] Add tests.
- [X] Start a simple Front-End
- [ ] Add templates for manual (csv, json) results and control points
- [ ] Improve Front-End
- [ ] Integrate ML/AI predictors
- [X] Before 2014 link is different (e.g. https://livetrail.net/histo/ecotrail2013/ instead of https://livetrail.net/histo/ecotrail_2013/)


### Scraping
- [X] BUG: for some races, control point code is not unique since it gets revisited in different laps (e.g. event 'tapalpa23', 2023, 'enigma')
- [X] Scraped timestamps are different (there is no day added and it gets back to 00:00:00 after 24h in race)
- [ ] There is a bug where if a time is missing and it is interpolated from previous (default) or next runner, it might be less than the previous checkpoint and we would then add 24h to this time --> It is highly improbable, we will leave it for now.
- [X] Get the name of the checkpoints from the website.
- [X] Set objective directly by time and not by position.
- [X] Get a list of available races in LiveTrail.
- [X] Rename Scraper to LiveTrail Scraper (others may come later)
- [X] Change camelCase style to snake_case style naming

### Relational DB
- [ ] BUG: When loading data, need to recheck category rankings.
- [ ] Change SQLite to Postgres ? --> when app will be dockerised
- [X] Add partial passing times (timing_points)
- [X] Add control points to DB
- [ ] Races with CSV results but no control points : create default ones with numbers
- [ ] *Tablelize* countries, categories.
- [X] Add tests.
- [ ] Add logic to control creation of objects (manage nullable or not fields) --> Seems impossible with old races
- [ ] Add Events getid to tests
- [ ] Add update race case into tests
- [X] Add Events to db
- [X] Add Races to DB
- [X] Need to reload races to DB due to identified bug (2696 from 3333 have a NULL departure_racetime)
- [X] Add results download
- [X] Load results to DB
- [X] Compute category results in DB
- [X] Design a way of having passing times in DB and not only final times
- [ ] Fix path for data and plots (env variable)
- [X] Not sure: Departure time doesn't seem always correct, will have to figure out another way of parsing it
- [X] add add Scraper.getRacesPhysicalDetails, Scraper.getRandomRunnerBib to tests
- [X] add results download + load to DB to lib instead of notebook + script
- [X] make a proper way to import to DB so imports can be scheduled : compare scraper.get_events_years to Event.get_events_years and scapre only diff


### ML/AI
- [ ] Add inference points from models
- [ ] Add modelling capabilities from own data, start simple (ensemble methods)
- [ ] Generate training file with simple variables (dist_total, D_total, d_total, dist_segment, dist_cumul, D_segment, D_cumul, d_segment, d_cumul, time)
- [ ] Research constrained methods (total_estimation = sum(sections_estimation))


### FrontEnd
- [ ] Make rows in my results pages links to races' results
- [X] Make header in my results pages clickable (for sorting)
- [ ] Add a switch button to tables between cumulative race time and time of the day(s)
- [ ] Add normalized pace plot and add a switch button between it and regular pace one. --> try with st.container
- [ ] Integrate printing version of times
- [ ] Show race profile from distance, D+ and D- data? Maybe too aproximative and need real gps data
- [ ] Objective graph is only paces, show times / normalised pace?
- [X] Bug when races include departure time in timing_points file


### BackEnd
- [ ] Add printing version of times
- [ ] Create a DB to scrape and store all results and information
- [ ] Add robustness to objective computation. i.e. if faster than first, compute std of the 5 samples and maybe decide to take less if it is too high (times too far appart)
- [X] Fix imports
- [X] Change camelCase style to snake_case style naming (Results)
- [X] Fix: Add support for front bug races having departuire in timing_points (Results)
- [X] Add this kind of races to tests (e.g. 'mbm' 2023 '42km')
- [X] BUG: Races with different start time per participant (e.g. 'Marathon du Mont-Blanc', '2014' , 'kmv', 402, 'KM Vertical').

### CI/CD
- [X] Create a CI
- [ ] Contenarize
- [ ] Create a CD Pipeline once contenarized
- [X] Add installation procedure
