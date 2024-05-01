import os
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup


class Scraper:
    base_url: str = "https://livetrail.net/histo/{event}_{year}"
    base_url2: str = "https://livetrail.net/histo/{event}{year}"

    def __init__(self, events: list[str] = [], years: list[str] = [], race: str = 'all') -> None:
        self.allEvents = self.getEvents()
        self.eventsYears = self.getEventsYears()
        self.events = events
        self.years = years
        self.race = race
        # self.date, self.startingTime, self.day = self.getRaceInfo()

    def _checkEventYear(self, e: str, y: str) -> None:
        if e not in list(self.allEvents.keys()) or y not in self.eventsYears[e]:
            raise ValueError(f"{e} is not a valid Live Trail race id for year {y}.")

    def _isValidYear(self, y):
        try:
            year = int(y)
            return len(y) == 4 and 1900 <= year <= 9999
        except ValueError:
            return False

    def setEvents(self, events: list[str]) -> None:
        self.events = events

    def setYears(self, years: list[str]) -> None:
        if all([self._isValidYear(y) for y in years]):
            self.years = years
        else:
            raise ValueError("Years contains a non valid number.")

    def setRace(self, race: str) -> None:
        self.race = race

    def getRaceInfo(self, bibN=1) -> dict:
        race_info = {}
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year)+f"/coureur.php?rech={bibN}"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year)+f"/coureur.php?rech={bibN}"
                    for url in [url1, url2]:
                        self._checkEventYear(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/coureur.php?rech={bibN}"
                        # Sending GET request to parse races' names
                        response = requests.get(url, timeout=20)
                        # Check if request was successful
                        if response.status_code == 200:
                            # 'race' is an id and 'name' a more human-readble version
                            race_info = self._parseRaceInfo(response.text)
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            race_info = {}
                            print("Failed to retrieve race info. Status code:", response.status_code)
                except ValueError as e:
                    print(e)
        return race_info

    def getRacesPhysicalDetails(self) -> dict:
        races_data = {}
        cp = self.getControlPoints()
        for race in cp.keys():
            race_data = {}
            race_data_tuple = cp[race].popitem()[1]
            race_data['distance'] = race_data_tuple[0]
            race_data['elevation_pos'] = race_data_tuple[1]
            race_data['elevation_neg'] = race_data_tuple[2]
            races_data[race] = race_data

        return races_data

    def _parseRaceInfo(self, xml_content: str) -> dict:
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
                race_info['date'] = e_tag['date'] if 'date' in e_tag else None # date of departure
                race_info['tz'] = e_tag['tz'] if 'date' in e_tag else None  # timezone of date
                race_info['hd'] = e_tag['hd'] if 'date' in e_tag else None  # departure time
                race_info['jd'] = e_tag['jd'] if 'date' in e_tag else None  # departure day of the week (1 Monday...7 Sunday)
                return race_info

    def parseTable(self, xml_content: str) -> pd.DataFrame:
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

    def _parseRaces(self, xml_content: str) -> dict:
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

    def getRandomRunnerBib(self):
        if len(self.events) > 1 or len(self.years) > 1:
            raise ValueError("This method is only available if there is only one event and year in Scraper.events ant Scraper.year")
        rr = {}
        races = self.getRaces()
        for event in self.events:
            for year in self.years:
                if year in races[event]:
                    rr[year] = {}
                    for race in races[event][year]:
                        df = self.getData(race)
                        if df is not None:
                            rr[year][race] = df.sort_index().iloc[0]['doss'] if not df.empty else None
                        else:
                            rr[year][race] = None
        return rr

    def getRaces(self) -> dict:
        fullRaces = {}
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year)+f"/passages.php"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year)+f"/passages.php"
                    for url in [url1, url2]:
                        self._checkEventYear(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                        # Sending GET request to parse races' names
                        response = requests.get(url, timeout=20)
                        # Check if request was successful
                        if response.status_code == 200:
                            # 'race' is an id and 'name' a more human-readble version
                            races = self._parseRaces(response.text)
                            fullRaces[event] = {year: races}
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            print("Failed to retrieve races' names. Status code:", response.status_code)
                except ValueError as e:
                    print(e)
        return fullRaces

    def downloadData(self, force_download=False) -> int:
        count = 0
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year)+f"/passages.php"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year)+f"/passages.php"
                    for url in [url1, url2]:
                        self._checkEventYear(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                        # Sending GET request to parse races' names
                        response = requests.get(url, timeout=20)
                        # Check if request was successful
                        if response.status_code == 200:
                            races = self._parseRaces(response.text)
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
                                folder_path = f'../../data/{event}'
                                if not os.path.exists(folder_path):
                                    os.makedirs(folder_path)
                                file_path = os.path.join(folder_path, f'{event}_{race}_{year}.csv')
                                if os.path.exists(file_path) and force_download is False:
                                    pass
                                else:
                                    # Sending POST request
                                    results_response = requests.post(url, data=data, timeout=20)
                                    # Check if request was successful
                                    if results_response.status_code == 200:
                                        df = self.parseTable(results_response.text)
                                        df.to_csv(os.path.join(folder_path, f'{event}_{race}_{year}.csv'), index=False)
                                    else:
                                        print(f"Failed to retrieve HTML table for event: {event} {year}, race: {race}. Status code:",
                                            results_response.status_code)
                                        count += 1
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            print("Failed to retrieve races' names. Status code:", response.status_code)
                            count += 1
                except ValueError as e:
                    print(e)
                    count += 1
                    pass
        # return number of errors
        return count

    def getData(self, race) -> pd.DataFrame:
        try:
            if len(self.events) > 1 or len(self.years) > 1:
                raise ValueError("This method is only available if there is only one event and year in Scraper.events ant Scraper.year")
            event = self.events[0]
            year = self.years[0]

            self._checkEventYear(event, year)
            # 'race' is an id and 'name' a more human-readble version
            # Data for the POST request
            data = {
                'course': race,
                'cat': 'scratch',
                'from': '1',
                'to': '1000000'  # To get all results
            }
            # Check if data already available or redownload:
            folder_path = f'../../data/{event}'
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            file_path = os.path.join(folder_path, f'{event}_{race}_{year}.csv')
            if os.path.exists(file_path):
                df = pd.read_csv(file_path, sep=',')
            else:
                # Sending POST request
                # url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                url1 = self.base_url.replace("{event}", event).replace("{year}", year)+f"/passages.php"
                url2 = self.base_url2.replace("{event}", event).replace("{year}", year)+f"/passages.php"
                for url in [url1, url2]:
                    results_response = requests.post(url, data=data, timeout=20)
                    # Check if request was successful
                    if results_response.status_code == 200:
                        df = self.parseTable(results_response.text)
                        break
                    else:
                        print(f"Failed to retrieve HTML table for event: {event} {year}, race: {race}. Status code:",
                            results_response.status_code)
            return df
        except ValueError as e:
            print(e)

    def _parseEventList(self, data) -> dict:
        data = json.loads(data)
        events_dict = {}
        for i in data['infoCourse']['cal'].items():
            events_dict[i[0]] = i[1]['nom']
        return events_dict

    def _parsePastEventList(self, data) -> dict:
        data = json.loads(data)
        events_dict = {}
        for i in data['calPass'].items():
            events_dict[i[0]] = list(i[1]['res'].keys())
        return events_dict

    def _parseControlPoints(self, data):
        soup = BeautifulSoup(data, 'lxml')
        p_tags = soup.find_all('points')
        controlPoints = {}
        for p_tag in p_tags:
            pt_tags = p_tag.find_all('pt')
            cps = {}
            for pt_tag in pt_tags:
                # Calculate the altitude difference between the current point and the first point
                # of the route and substract this quantity from cummulated elevaation gain.
                elev_loss = int(pt_tag['d']) - (int(pt_tag['a']) - int(pt_tags[0]['a']))
                # {'cp_name' : (acc_dist, acc_elev+, -acc_elev-)}
                cps[pt_tag['n']] = (float(pt_tag['km']), int(pt_tag['d']), -elev_loss)
            controlPoints[p_tag['course']] = cps
        return controlPoints

    def getEvents(self) -> dict:
        url = "https://livetrail.net/phpFonctions/homeFunctions.php"
        # Data for the POST request
        data = {
            'mode': 'dispAllEvents',
            'type': 'livetrail.net'
        }
        # Sending POST request
        response = requests.post(url, data=data, timeout=20)
        # Check if request was successful
        if response.status_code == 200:
            events_dict = self._parseEventList(response.text)
        else:
            print("Failed to retrieve Live Trail's event list. Status code:",
                  response.status_code)
        return events_dict

    def getEventsYears(self) -> dict:
        url = "https://livetrail.net/phpFonctions/eventFunctions.php"
        # Data for the POST request
        data = {
            'mode': 'dispEventPass',
            'type': 'livetrail.net'
        }
        # Sending POST request
        response = requests.post(url, data=data, timeout=20)
        # Check if request was successful
        if response.status_code == 200:
            events_dict = self._parsePastEventList(response.text)
        else:
            print("Failed to retrieve Live Trail's event list. Status code:",
                  response.status_code)
        return events_dict

    def getControlPoints(self) -> dict:
        count = 0
        controlPoints = {}
        for event in self.events:
            for year in self.years:
                try:
                    url1 = self.base_url.replace("{event}", event).replace("{year}", year)+"/parcours.php"
                    url2 = self.base_url2.replace("{event}", event).replace("{year}", year)+"/parcours.php"
                    for url in [url1, url2]:
                        self._checkEventYear(event, year)
                        # URL of the website
                        # url = f"https://livetrail.net/histo/{event}_{year}/parcours.php"
                        # Sending GET request to parse races' names
                        response = requests.get(url, timeout=20)
                        # Check if request was successful
                        if response.status_code == 200:
                            controlPoints = self._parseControlPoints(response.text)
                            # if url1 fails, some old pages url is like in 2
                            break
                        else:
                            print(f"Failed to retrieve races' control points for {event} {year}. Status code:", response.status_code)
                            count += 1
                except ValueError as e:
                    print(e)
                    count += 1
                    pass
        # return number of errors
        return controlPoints
