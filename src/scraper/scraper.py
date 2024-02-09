import os
import requests
import pandas as pd
from bs4 import BeautifulSoup
import pandas as pd


class Scraper:
    def __init__(self, events: list[str], years: list[str], race: str = 'all') -> None:
        self.events = events
        self.years = years
        self.race = race
        print()

    def setEvent(self, events: list[str]) -> None:
        self.event = events
        
    def setYear(self, years: list[str]) -> None:
        self.year = years
    
    def setRace(self, race: str) -> None:
        self.race = race

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

    def getRaces(self, xml_content: str) -> dict:
        # Parse the XML content
        soup = BeautifulSoup(xml_content, 'xml')

        # Find the <courses> tag
        courses_tag = soup.find('courses')#'select', id='chxCourse')

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
    
    def getData(self) -> int:
        count = 0
        for event in self.events:
            for year in self.years:
                # URL of the website
                url = f"https://livetrail.net/histo/{event}_{year}/passages.php"
                # Sending GET request to parse races' names
                response = requests.get(url)
                # Check if request was successful
                if response.status_code == 200:
                    races = self.getRaces(response.text)
                    # 'race' is an id and 'name' a more human-readble version
                    for  race, name in races.items():
                        # Data for the POST request
                        data = {
                            'course': race,
                            'cat': 'scratch',
                            'from': '1',
                            'to': '1000000' # To get all results
                        }
                        # Sending POST request
                        results_response = requests.post(url, data=data)
                        # Check if request was successful
                        if results_response.status_code == 200:
                            df = self.parseTable(results_response.text)
                            folder_path = f'../../data/{event}'
                            if not os.path.exists(folder_path):
                                os.makedirs(folder_path)
                            df.to_csv(os.path.join(folder_path,f'{event}_{race}_{year}.csv'), index=False)
                        else:
                            print("Failed to retrieve HTML table for event: {event} {year}, race: {race}. Status code:",
                                response.status_code)
                            count += 1
                else:
                    print("Failed to retrieve races' names. Status code:", response.status_code)
                    count += 1
        # return number of errors
        return count