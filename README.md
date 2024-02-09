# ML Trail Library

Work in progress.

Lib to process results, make analysis of Trail running races and eventually build models to predict performances.

## TO-DO list
- [X] Automatically parse LiveTrail data.
- [ ] Add tests.

### Scraping
- [X] Scraped timestamps are different (there is no day added and it gets back to 00:00:00 after 24h in race)
- [ ] There is a bug where if a time is missing and it is interpolated from previous (default) or next runner, it might be less than the previous checkpoint and we would then add 24h to this time --> It is highly improbable, we will leave it for now.
- [ ] Get the name of the checkpoints from the website.
- [ ] Set objective directly by time and not by position.
- [ ] Get a list of available races in LiveTrail.
