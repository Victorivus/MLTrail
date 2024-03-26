import pytest
import sys
sys.path.append('../src/')
from scraper.scraper import Scraper
import pandas as pd

# Test case for _checkEventYear method
def test_check_event_valid():
    scraper = Scraper()
    with pytest.raises(ValueError):
        scraper._checkEventYear("invalid_event", "2022")
        

# Test case for _checkEventYear method
def test_check_event_year_valid():
    scraper = Scraper()
    with pytest.raises(ValueError):
        scraper._checkEventYear("transgrancanaria", "1995")


# Test case for setYears and _checkEventYear method
def test_check_year_valid():
    scraper = Scraper()
    with pytest.raises(ValueError):
        scraper.setYears(["1995", "abc", "2023"])


# Test case for setYears method
def test_check_year_valid():
    scraper = Scraper()
    scraper.setYears(["2015", "2023"])
    assert scraper.years == ["2015", "2023"]


# Test case for getControlPoints and _parseControlPoints method
def test_get_control_points():
    # Transgrancanaria 2023 data
    control_points = {
                        'Salida Clasic': (0.0, 0, 0),
                        'Tenoya': (11.43, 348, -188),
                        'Arucas': (19.44, 704, -482),
                        'Teror': (31.95, 1509, -922),
                        'Fontanales': (43.55, 2463, -1461),
                        'El Hornillo': (53.51, 3089, -2339),
                        'Artenara': (67.11, 4156, -2961),
                        'Tejeda': (79.63, 4919, -3878),
                        'Roque Nublo': (88.15, 5869, -4128),
                        'Garañon': (91.32, 6042, -4372),
                        'Tunte': (104.26, 6369, -5483),
                        'Ayagaures': (116.57, 6803, -6500),
                        'Meta Parque Sur': (130.74, 7000, -6970)
                    }
    scraper = Scraper(events=["transgrancanaria"], years=["2023"])
    cp = scraper.getControlPoints()['classic']
    assert cp == control_points
    
    # Sainté-Lyon 2021 data
    control_points = {  
                        'Saint Etienne': (0.0, 0, 0),
                        'Saint-Christo-en-Jarez': (18.14, 602, -338),
                        'Sainte-Catherine': (31.96, 1109, -908),
                        'Le Camp - Saint-Genou': (45.01, 1522, -1396),
                        'Soucieu-en-Jarrest': (55.86, 1736, -1863),
                        'Chaponost': (65.38, 1857, -2041),
                        'Lyon': (78.3, 2126, -2448)
                    }
    scraper = Scraper(events=["saintelyon"], years=["2021"])
    cp = scraper.getControlPoints()['78km']
    assert cp == control_points

# Test case for downloadData method
def test_download_data():
    scraper = Scraper(events=["transgrancanaria"], years=["2023"])
    scraper.downloadData()
    results_raw = pd.read_csv('../data/transgrancanaria/transgrancanaria_classic_2023.csv', sep=',')
    data = {
        'n': 4,
        'doss': 18,
        'nom': 'BUTACI',
        'prenom': 'Raul',
        'cat': 'MA30H',
        '00': '00:00:13',
        '21': '00:49:34',
        '23': '01:33:48',
        '25': '02:49:13',
        '27': '04:10:40',
        '29': '05:19:47',
        '31': '06:58:30',
        '33': '08:27:01',
        '35': '09:51:18',
        '41': '10:16:20',
        '43': '11:35:38',
        '45': '12:54:03',
        '110': '14:15:53'
    }
    assert pd.Series(data, name='3').equals(results_raw.iloc[3])

# Test case for getEvents method
def test_get_events():
    scraper = Scraper()
    # On 10/02/2024 there are 323 events
    assert len(scraper.getEvents()) > 322

# Test case for getEventsYears method
def test_get_events_years():
    evs = Scraper().getEventsYears()
    # On 10/02/2024 there are 3034 of tuples event,year
    assert sum([len(e) for e in evs]) > 3033
    

# Test case for getRaces method
def test_get_races():
    data = {'transgrancanaria':
        {'2023':
            {'classic': 'Classic 128 KM',
             'advance': 'Advanced 84 KM',
             'maraton': 'Maraton 45 KM',
             'starter': 'Starter 24 KM',
             'promo': 'Promo',
             'youth': 'Youth',
             'family': 'Family'
             }
        }
    }
    races = Scraper(events=["transgrancanaria"], years=["2023"]).getRaces()
    assert data == races    

# Test case for getData method
def test_get_data():
    data = {
        'n': 4,
        'doss': 18,
        'nom': 'BUTACI',
        'prenom': 'Raul',
        'cat': 'MA30H',
        '00': '00:00:13',
        '21': '00:49:34',
        '23': '01:33:48',
        '25': '02:49:13',
        '27': '04:10:40',
        '29': '05:19:47',
        '31': '06:58:30',
        '33': '08:27:01',
        '35': '09:51:18',
        '41': '10:16:20',
        '43': '11:35:38',
        '45': '12:54:03',
        '110': '14:15:53'
    }
    
    scr =  Scraper(events=["transgrancanaria"], years=["2023"])
    assert pd.Series(data, name='3').equals(scr.getData('classic').iloc[3])

# Test case for getRaceInfo method
def test_get_race_info():
    race_info = {'date': '2024-02-24', 'tz': '0', 'hd': '00:00:03', 'jd': '6'}
    scr =  Scraper(events=["transgrancanaria"], years=["2024"])
    sorted_dict1 = sorted(race_info.items())
    sorted_dict2 = sorted(scr.getRaceInfo(bibN=20).items())
    assert sorted_dict1 == sorted_dict2, "Race info method Failed"
