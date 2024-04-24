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


### Scraping
- [X] Scraped timestamps are different (there is no day added and it gets back to 00:00:00 after 24h in race)
- [ ] There is a bug where if a time is missing and it is interpolated from previous (default) or next runner, it might be less than the previous checkpoint and we would then add 24h to this time --> It is highly improbable, we will leave it for now.
- [X] Get the name of the checkpoints from the website.
- [X] Set objective directly by time and not by position.
- [X] Get a list of available races in LiveTrail.
- [ ] Rename Scraper to LiveTrail Scraper (others may come later)


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
- [ ] Add robustness to objective computation. i.e. if faster than first, compute std of the 5 samples and maybe decide to take less if it is too high (times too far appart)
- [ ] Fix imports
- [ ] KNOWN BUGS / VORNER CASES TO CHECK:
        - [ ] UTMB gives - [ ] Some races (e.g. PENYAGOLOSA TRAILS 2023 CSP) do not order df properly (eg 358, 359, 360, 0, 1, 2...) so the graph shown is not correct. Correct graph computation to fix this errors and/or understand why this ordering occurs.


### CI/CD
- [ ] Create a CI/CD Pipeline
- [ ] Contenarize
- [ ] Add installation procedure
