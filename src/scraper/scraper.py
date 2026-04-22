import os
import json
import time
import random
import logging
import warnings
import requests
import pandas as pd
from bs4 import BeautifulSoup
from bs4 import GuessedAtParserWarning
from bs4 import XMLParsedAsHTMLWarning
from config import get_config

logger = logging.getLogger(__name__)

# Suppress the XMLParsedAsHTMLWarning
warnings.filterwarnings('ignore', category=GuessedAtParserWarning)
warnings.filterwarnings("ignore", message="XMLParsedAsHTMLWarning")
warnings.filterwarnings("ignore", message=".*XMLParsedAsHTMLWarning.*")
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", category=UserWarning, module='bs4')


class LiveTrailScraper:
    base_url: str = "https://livetrail.net/histo/{event}_{year}"
    base_url2: str = "https://livetrail.net/histo/{event}{year}"
    data_path = get_config().data_dir_path

    _MAX_RETRIES = 3
    _BASE_DELAY = 1.0   # min seconds between requests
    _MAX_DELAY = 3.0     # max seconds between requests
    _BACKOFF_BASE = 2.0  # exponential backoff base (2s, 4s, 8s)

    def __init__(self, events: list[str] = [], years: list[str] = [],
                 race: str = 'all') -> None:
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.allEvents = self.get_events()
        self.eventsYears = self.get_events_years()
        self.events = events
        self.years = years
        self.race = race

    def _request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', 20)
        for attempt in range(self._MAX_RETRIES + 1):
            # Polite delay before each request
            delay = random.uniform(self._BASE_DELAY, self._MAX_DELAY)
            time.sleep(delay)
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self._MAX_RETRIES:
                        backoff = self._BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning("HTTP %s from %s — retrying in %.1fs (attempt %d/%d)",
                                       response.status_code, url, backoff, attempt + 1, self._MAX_RETRIES)
                        time.sleep(backoff)
                        continue
                return response
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < self._MAX_RETRIES:
                    backoff = self._BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning("Connection error on %s — retrying in %.1fs (attempt %d/%d): %s",
                                   url, backoff, attempt + 1, self._MAX_RETRIES, e)
                    time.sleep(backoff)
                else:
                    logger.error("Request failed after %d retries: %s", self._MAX_RETRIES, url)
                    raise

    def _check_event_year(self, e: str, y: str) -> None:
        if e not in list(self.allEvents.keys()) or y not in self.eventsYears[e]:
            raise ValueError(f"{e} is not a valid Live Trail race id for year {y}.")

    def _is_valid_year(self, y):
        try:
            year = int(y)
            return len(y) == 4 and 1900 <= year <= 9999
        except ValueError:
            return False

    def set_events(self, events: list[str]) -> None:
        self.events = events

    def set_years(self, years: list[str]) -> None:
        if all([self._is_valid_year(y) for y in years]):
            self.years = years
        else:
            raise ValueError("Years contains a non valid number.")

    def set_race(self, race: str) -> None:
        self.race = race

    def get_race_info(self, bib_n=1) -> dict:
        race_info = {}
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year) + f"/coureur.php?rech={bib_n}"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year) + f"/coureur.php?rech={bib_n}"
                    for url in [url1, url2]:
                        self._check_event_year(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/coureur.php?rech={bib_n}"
                        # Sending GET request to parse races' names
                        response = self._request('GET', url)
                        # Check if request was successful
                        if response.status_code == 200:
                            # 'race' is an id and 'name' a more human-readble version
                            race_info = self._parse_race_info(response.text)
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            race_info = {}
                            logger.warning("Failed to retrieve race info. Status code: %s", response.status_code)
                except ValueError as e:
                    logger.warning("%s", e)
        return race_info

    def get_races_physical_details(self) -> dict:
        races_data = {}
        cp, _ = self.get_control_points()
        for race in cp.keys():
            race_data = {}
            race_data_tuple = cp[race].popitem()[1]
            race_data['distance'] = race_data_tuple[0]
            race_data['elevation_pos'] = race_data_tuple[1]
            race_data['elevation_neg'] = race_data_tuple[2]
            races_data[race] = race_data

        return races_data

    def _parse_race_info(self, xml_content: str) -> dict:
        # Parse the XML content
        soup = BeautifulSoup(xml_content, 'xml')

        # Find the <pass> tag
        pass_tag = soup.find('pass')  # 'select', id='chxCourse')

        # Find all <e> tags within the <pass> tag
        e_tags = pass_tag.find_all('e')

        # Create a dictionary to store id and n attributes
        race_info = {}
        # Extract id and n attributes from each <c> tag
        for e_tag in e_tags:
            if e_tag['idpt'] == '0':
                race_info['date'] = e_tag['date'] if e_tag.has_attr('date') else None  # date of departure
                race_info['tz'] = e_tag['tz'] if e_tag.has_attr('tz') else None  # timezone of date
                race_info['hd'] = e_tag['hd'] if e_tag.has_attr('hd') else None  # departure time
                race_info['jd'] = e_tag['jd'] if e_tag.has_attr('jd') else None  # departure day of the week (1 Monday...7 Sunday)
                return race_info

    def _parse_table(self, xml_content: str) -> pd.DataFrame:
        # Parse the XML content
        soup = BeautifulSoup(xml_content, 'xml')

        # Find all <l> tags (rows)
        rows = soup.find_all('l')

        # Create an empty list to store row data
        data = []

        # Extract data from each row
        for row in rows:
            row_data = {}
            row_data['n'] = row['n']
            row_data['doss'] = row['doss']
            row_data['nom'] = row['nom']
            row_data['prenom'] = row['prenom']
            row_data['cat'] = row['cat']
            points = row.find_all('p')
            for point in points:
                row_data[point['idpt']] = point['h']
            data.append(row_data)

        # Create a DataFrame from the extracted data
        df = pd.DataFrame(data)
        return df

    def _parse_races(self, xml_content: str) -> dict:
        # Parse the XML content
        soup = BeautifulSoup(xml_content, 'xml')

        # Find the <courses> tag
        courses_tag = soup.find('courses')  # 'select', id='chxCourse')

        # Find all <c> tags within the <courses> tag
        c_tags = courses_tag.find_all('c')

        # Create a dictionary to store id and n attributes
        result_dict = {}

        # Extract id and n attributes from each <c> tag
        for c_tag in c_tags:
            c_id = c_tag['id']
            c_n = c_tag['n']
            result_dict[c_id] = c_n

        return result_dict

    def get_random_runner_bib(self, data_path=None):
        if len(self.events) > 1 or len(self.years) > 1:
            raise ValueError("This method is only available if there is only one event and year in LiveTrailScraper.events ant LiveTrailScraper.year")
        if not data_path:
            data_path = os.path.join(self.data_path, 'csv')
        rr = {}
        races = self.get_races()
        for event in self.events:
            for year in self.years:
                if year in races[event]:
                    rr[year] = {}
                    for race in races[event][year]:
                        df = self.get_data(race, data_path=data_path)
                        if df is not None:
                            rr[year][race] = df.sort_index().iloc[0]['doss'] if not df.empty else None
                        else:
                            rr[year][race] = None
        return rr

    def get_races(self) -> dict:
        '''
            Get all races information in the format: {event: year: races}
                where races is a dictionary containing code: full_name.

            Here is an example for Transgrancanaria 2023:
            {
                'transgrancanaria':
                    {
                        '2023':
                            {
                                'classic': 'Classic 128 KM',
                                'advance': 'Advanced 84 KM',
                                'maraton': 'Maraton 45 KM',
                                'starter': 'Starter 24 KM',
                                'promo': 'Promo',
                                'youth': 'Youth',
                                'family': 'Family'
                            }
                    }
            }

        '''
        full_races = {}
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year) + "/passages.php"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year) + "/passages.php"
                    for url in [url1, url2]:
                        self._check_event_year(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                        # Sending GET request to parse races' names
                        response = self._request('GET', url)
                        # Check if request was successful
                        if response.status_code == 200:
                            # 'race' is an id and 'name' a more human-readble version
                            races = self._parse_races(response.text)
                            full_races[event] = {year: races}
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            logger.warning("Failed to retrieve races' names. Status code: %s", response.status_code)
                except ValueError as e:
                    logger.warning("%s", e)
        return full_races

    def download_data(self, data_path=None, force_download=False) -> int:
        if not data_path:
            data_path = os.path.join(self.data_path, 'csv')
        count = 0
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year) + "/passages.php"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year) + "/passages.php"
                    for url in [url1, url2]:
                        self._check_event_year(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                        # Sending GET request to parse races' names
                        response = self._request('GET', url)
                        # Check if request was successful
                        if response.status_code == 200:
                            races = self._parse_races(response.text)
                            # 'race' is an id and 'name' a more human-readble version
                            for race, name in races.items():
                                # Data for the POST request
                                data = {
                                    'course': race,
                                    'cat': 'scratch',
                                    'from': '1',
                                    'to': '1000000'  # To get all results
                                }
                                # Check if data already available or redownload:
                                folder_path = os.path.join(data_path, event)
                                if not os.path.exists(folder_path):
                                    os.makedirs(folder_path)
                                file_path = os.path.join(folder_path, f'{event}_{race}_{year}.csv')
                                if os.path.exists(file_path) and force_download is False:
                                    pass
                                else:
                                    # Sending POST request
                                    results_response = self._request('POST', url, data=data)
                                    # Check if request was successful
                                    if results_response.status_code == 200:
                                        df = self._parse_table(results_response.text)
                                        df.to_csv(os.path.join(folder_path, f'{event}_{race}_{year}.csv'), index=False)
                                    else:
                                        logger.warning("Failed to retrieve HTML table for event: %s %s, race: %s. Status code: %s",
                                                       event, year, race, results_response.status_code)
                                        count += 1
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            logger.warning("Failed to retrieve races' names. Status code: %s", response.status_code)
                            count += 1
                except ValueError as e:
                    logger.warning("%s", e)
                    count += 1
        # return number of errors
        return count

    def get_data(self, race, data_path=None) -> pd.DataFrame:
        try:
            if len(self.events) > 1 or len(self.years) > 1:
                raise ValueError("This method is only available if there is only one event and year in LiveTrailScraper.events and LiveTrailScraper.year")
            if not data_path:
                data_path = os.path.join(self.data_path, 'csv')
            event = self.events[0]
            year = self.years[0]

            self._check_event_year(event, year)
            # 'race' is an id and 'name' a more human-readble version
            # Data for the POST request
            data = {
                'course': race,
                'cat': 'scratch',
                'from': '1',
                'to': '1000000'  # To get all results
            }
            # Check if data already available or redownload:
            folder_path = os.path.join(data_path, event)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            file_path = os.path.join(folder_path, f'{event}_{race}_{year}.csv')
            if os.path.exists(file_path):
                df = pd.read_csv(file_path, sep=',')
            else:
                # Sending POST request
                # url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                url1 = self.base_url.replace("{event}", event).replace("{year}", year) + "/passages.php"
                url2 = self.base_url2.replace("{event}", event).replace("{year}", year) + "/passages.php"
                for url in [url1, url2]:
                    results_response = self._request('POST', url, data=data)
                    # Check if request was successful
                    if results_response.status_code == 200:
                        df = self._parse_table(results_response.text)
                        break
                    else:
                        logger.warning("Failed to retrieve HTML table for event: %s %s, race: %s. Status code: %s",
                                       event, year, race, results_response.status_code)
            return df
        except ValueError as e:
            logger.warning("%s", e)

    def _parse_event_list(self, data) -> dict:
        data = json.loads(data)
        events_dict = {}
        for i in data['infoCourse']['cal'].items():
            events_dict[i[0]] = i[1]['nom']
        return events_dict

    def _parse_past_event_list(self, data) -> dict:
        data = json.loads(data)
        events_dict = {}
        for i in data['calPass'].items():
            events_dict[i[0]] = list(i[1]['res'].keys())
        return events_dict

    def _clean_control_name(self, cps, name):
        if name in cps:
            if name[0].isdigit():
                name = str(int(name[0]) + 1) + name[1:]
                return self._clean_control_name(cps, name)
            else:
                name = '2-' + name
                return self._clean_control_name(cps, name)
        else:
            return name

    def _parse_control_points(self, data):
        soup = BeautifulSoup(data, 'lxml')
        p_tags = soup.find_all('points')
        control_points = {}
        control_points_names = {}
        for p_tag in p_tags:
            pt_tags = p_tag.find_all('pt')
            cps = {}
            cps_names = {}
            for pt_tag in pt_tags:
                # Calculate the altitude difference between the current point and the first point
                # of the route and substract this quantity from cummulated elevaation gain.
                elev_loss = int(pt_tag['d']) - (int(pt_tag['a']) - int(pt_tags[0]['a']))
                # {'cp_name' : (acc_dist, acc_elev+, -acc_elev-)}
                if pt_tag['nc'] in cps:
                    pt_tag['nc'] = self._clean_control_name(cps, pt_tag['nc'])
                cps[pt_tag['nc']] = (float(pt_tag['km']), int(pt_tag['d']), -elev_loss)
                cps_names[pt_tag['nc']] = pt_tag['n']
            control_points[p_tag['course']] = cps
            control_points_names[p_tag['course']] = cps_names
        return control_points, control_points_names

    def get_events(self) -> dict:
        url = "https://livetrail.net/phpFonctions/homeFunctions.php"
        # Data for the POST request
        data = {
            'mode': 'dispAllEvents',
            'type': 'livetrail.net'
        }
        # Sending POST request
        response = self._request('POST', url, data=data)
        # Check if request was successful
        if response.status_code == 200:
            events_dict = self._parse_event_list(response.text)
        else:
            logger.warning("Failed to retrieve Live Trail's event list. Status code: %s",
                         response.status_code)
        return events_dict

    def get_events_years(self) -> dict:
        url = "https://livetrail.net/phpFonctions/eventFunctions.php"
        # Data for the POST request
        data = {
            'mode': 'dispEventPass',
            'type': 'livetrail.net'
        }
        # Sending POST request
        response = self._request('POST', url, data=data)
        # Check if request was successful
        if response.status_code == 200:
            events_dict = self._parse_past_event_list(response.text)
        else:
            logger.warning("Failed to retrieve Live Trail's event list. Status code: %s",
                         response.status_code)
        return events_dict

    def probe_current_year_events(self, year: str = None,
                                   skip_events: set = None) -> list[str]:
        '''
            Discover events that have already raced in ``year`` but aren't yet in
            LiveTrail's archived-years feed (``dispEventPass``).

            For each event known to LiveTrail, issues a single GET to
            ``passages.php`` for the target year. On a 200 response whose XML
            body contains a ``<courses>`` tag, ``year`` is appended to
            ``self.eventsYears[event]`` so that ``_check_event_year`` accepts
            the pair and the ``--update`` diff picks it up.

            ``skip_events`` is a set of event codes that should not be probed —
            typically those already stored for ``year`` in the caller's DB. This
            prevents re-probing (and re-downloading) events every run until
            LiveTrail catches up on its archive feed.

            Returns the list of event codes that were newly discovered.
        '''
        import datetime as _dt
        if year is None:
            year = str(_dt.date.today().year)
        skip_events = skip_events or set()

        discovered = []
        for event in self.allEvents.keys():
            if event in skip_events:
                continue
            if year in self.eventsYears.get(event, []):
                continue
            for template in (self.base_url, self.base_url2):
                url = template.replace("{event}", event).replace("{year}", year) + "/passages.php"
                try:
                    response = self._request('GET', url)
                except requests.RequestException:
                    break
                if response is None or response.status_code != 200:
                    continue
                # Any passages.php hit returns XML. Missing events still hit 200
                # for the root LiveTrail 404 page, so confirm the <courses> tag.
                if '<courses>' not in response.text:
                    continue
                self.eventsYears.setdefault(event, []).insert(0, year)
                discovered.append(event)
                logger.info("Discovered %s %s via current-year probe", event, year)
                break
        logger.info("Current-year probe for %s found %d new event(s)", year, len(discovered))
        return discovered

    def get_control_points(self) -> dict:
        count = 0
        control_points = {}
        control_points_names = {}
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year) + "/parcours.php"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year) + "/parcours.php"
                    for url in [url1, url2]:
                        self._check_event_year(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/parcours.php"
                        # Sending GET request to parse races' names
                        response = self._request('GET', url)
                        # Check if request was successful
                        if response.status_code == 200:
                            control_points, control_points_names = self._parse_control_points(response.text)
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            logger.warning("Failed to retrieve races' control points for %s %s. Status code: %s",
                                         event, year, response.status_code)
                            count += 1
                except ValueError as e:
                    logger.warning("%s", e)
                    count += 1
        # return number of errors
        return control_points, control_points_names
