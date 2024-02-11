# ML Trail Library

Work in progress.

Lib to process results, make analysis of Trail running races and eventually build models to predict performances.

## TO-DO list
- [X] Automatically parse LiveTrail data.
- [X] Add tests.
- [X] Start a simple Front-End
- [ ] Add templates for manual (csv, json) results and control points
- [ ] Improve Front-End
- [ ] Integrate ML/AI predictors
- 
### Scraping
- [X] Scraped timestamps are different (there is no day added and it gets back to 00:00:00 after 24h in race)
- [ ] There is a bug where if a time is missing and it is interpolated from previous (default) or next runner, it might be less than the previous checkpoint and we would then add 24h to this time --> It is highly improbable, we will leave it for now.
- [X] Get the name of the checkpoints from the website.
- [X] Set objective directly by time and not by position.
- [X] Get a list of available races in LiveTrail.
- [ ] Rename to LiveTrail Scraper (others may come)

### ML/AI
- [ ] Add inference points from models
- [ ] Add modelling capabilities from own data, start simple (ensemble methods)

### FrontEnd
- [ ] Integrate printing version of times

### FrontEnd
- [ ] Add printing version of times
