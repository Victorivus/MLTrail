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

# Launch web app
Launch the following command:

```
streamlit run front/app.py
```

# Collaborating

## feat/rel_db branch TO-DO list
- [ ] *Tablelize* countries, categories.
- [X] Add tests.
- [ ] Add logic to control creation of objects (manage nullable or not fields) --> Seems impossible with old races
- [ ] Add Events getid to tests
- [ ] Add update race case into tests
- [X] Add Events to db
- [X] Add Races to DB
- [ ] Need to reload races to DB due to identified bug (2696 from 3333 have a NULL departure_racetime)
- [X] Add results download
- [ ] Load results to DB
- [ ] Fix path for data and plots (env variable)
- [ ] Departure time doesn't seem always correct, will have to figure out another way of parsing it
- [X] add add Scraper.getRacesPhysicalDetails, Scraper.getRandomRunnerBib to tests
- [ ] add results download + load to DB
- [ ] make a proper way to import to DB so imports can be scheduled

## TO-DO list
- [X] Automatically parse LiveTrail data.
- [X] Add tests.
- [X] Start a simple Front-End
- [ ] Add templates for manual (csv, json) results and control points
- [ ] Improve Front-End
- [ ] Integrate ML/AI predictors
- [ ] Before 2014 link is different (e.g. https://livetrail.net/histo/ecotrail2013/ instead of https://livetrail.net/histo/ecotrail_2013/)


### Scraping
- [X] Scraped timestamps are different (there is no day added and it gets back to 00:00:00 after 24h in race)
- [ ] There is a bug where if a time is missing and it is interpolated from previous (default) or next runner, it might be less than the previous checkpoint and we would then add 24h to this time --> It is highly improbable, we will leave it for now.
- [X] Get the name of the checkpoints from the website.
- [X] Set objective directly by time and not by position.
- [X] Get a list of available races in LiveTrail.
- [X] Rename Scraper to LiveTrail Scraper (others may come later)
- [X] Change camelCase style to snake_case style naming


### ML/AI
- [ ] Add inference points from models
- [ ] Add modelling capabilities from own data, start simple (ensemble methods)


### FrontEnd
- [ ] Add a switch button to tables between cumulative race time and time of the day(s)
- [ ] Add normalized pace plot and add a switch button between it and regular pace one.
- [ ] Integrate printing version of times
- [ ] Show race profile from distance, D+ and D- data? Maybe too aproximative and need real gps data
- [ ] Objective graph is only paces, show times / normalised pace?


### BackEnd
- [ ] Add printing version of times
- [ ] Create a DB to scrape and store all results and information
- [ ] Add robustness to objective computation. i.e. if faster than first, compute std of the 5 samples and maybe decide to take less if it is too high (times too far appart)
- [X] Fix imports
- [ ] Change camelCase style to snake_case style naming (Results)

### CI/CD
- [ ] Create a CI/CD Pipeline
- [ ] Contenarize
- [X] Add installation procedure
