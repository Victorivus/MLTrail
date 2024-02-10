import pytest
import sys
sys.path.append('../src/')
from results.results import Results
import pandas as pd
import numpy as np


# Define a fixture for a sample instance of the Results class
@pytest.fixture
def sample_results():
    # Transgrancanaria 2023 data
    # it includes a NaN for Green TAYLER and a retired person to be filtered out
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
    data = {
                        'n': [2, 3, 4, 500],
                        'doss': [14, 17, 18, 500],
                        'nom': ['ARSÉNIO', 'GREEN', 'BUTACI', 'TEST'],
                        'prenom': ['Miguel', 'Tyler', 'Raul', 'Test'],
                        'cat': ['EL H', 'MA30H', 'MA30H', 'EL H'],
                        'Salida Clasic': ['00:00:13', '00:00:13', '00:00:13',  '00:00:13'],
                        'Tenoya': ['00:51:13', '00:50:46', '00:49:34', '00:49:34'],
                        'Arucas': ['01:36:42', '01:35:19', '01:33:48', '01:33:48'],
                        'Teror': ['02:52:18', '02:52:42', '02:49:13', '02:49:13'],
                        'Fontanales': ['04:14:16', '04:14:19', '04:10:40', '04:10:40'],
                        'El Hornillo': ['05:28:13', '05:28:31', '05:19:47', '05:19:47'],
                        'Artenara': ['07:12:03', '07:09:21', '06:58:30', '06:58:30'],
                        'Tejeda': ['08:34:43', '08:36:47', '08:27:01', np.nan],
                        'Roque Nublo': ['09:50:27', np.nan, '09:51:18', np.nan],
                        'Garañon': ['10:12:13', '10:20:43', '10:16:20', np.nan],
                        'Tunte': ['11:26:32', '11:38:20', '11:35:38', np.nan],
                        'Ayagaures': ['12:34:22', '12:52:21', '12:54:03', np.nan],
                        'Meta Parque Sur': ['13:44:50', '14:06:59', '14:15:53', np.nan]
    }
    results_raw = pd.DataFrame(data)#pd.Series(data, name='3')).T
    results_raw.index = ['1', '2', '3', '500']
    control_points.pop(next(iter(control_points))) # Remove 1st CP (starting line)
    times = results_raw[control_points.keys()]
    return Results(control_points, times, offset=0, cleanDays=False)


# Test case for getData method
def test_init(sample_results):
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
    data = {
                        'n': 4,
                        'doss': 18,
                        'nom': 'BUTACI',
                        'prenom': 'Raul',
                        'cat': 'MA30H',
                        'Salida Clasic': '00:00:13',
                        'Tenoya': '00:49:34',
                        'Arucas': '01:33:48',
                        'Teror': '02:49:13',
                        'Fontanales': '04:10:40',
                        'El Hornillo': '05:19:47',
                        'Artenara': '06:58:30',
                        'Tejeda': '08:27:01',
                        'Roque Nublo': '09:51:18',
                        'Garañon': '10:16:20',
                        'Tunte': '11:35:38',
                        'Ayagaures': '12:54:03',
                        'Meta Parque Sur': '14:15:53'
    }
    
    results_raw = pd.DataFrame(pd.Series(data, name='3')).T
    control_points.pop(next(iter(control_points))) # Remove 1st CP (starting line)
    times = results_raw[control_points.keys()]
    print(sample_results.times.loc['3'])
    assert all(sample_results.times.loc['3'] == times)


# Test case for paces computation
def test_get_paces(sample_results):
    # Raul BUTACI in Transgrancanaria 2023
    data = {
            'Tenoya': '0:04:20',
            'Arucas': '0:05:31',
            'Teror': '0:06:01',
            'Fontanales': '0:07:01',
            'El Hornillo': '0:06:56',
            'Artenara': '0:07:15',
            'Tejeda': '0:07:04',
            'Roque Nublo': '0:09:53',
            'Garañon': '0:07:53',
            'Tunte': '0:06:07',
            'Ayagaures': '0:06:22',
            'Meta Parque Sur': '0:05:46'
    }
    
    paces = pd.DataFrame(pd.Series(data, name='3')).T
    assert all(sample_results.paces.loc['3'] == paces)


# Test case for paces computation
def test_get_pacesNorm(sample_results):
    # Raul BUTACI in Transgrancanaria 2023
    data = {
            'Tenoya': '0:03:19',
            'Arucas': '0:05:07',
            'Teror': '0:04:40',
            'Fontanales': '0:05:10',
            'El Hornillo': '0:09:17',
            'Artenara': '0:05:28',
            'Tejeda': '0:08:03',
            'Roque Nublo': '0:05:25',
            'Garañon': '0:10:10',
            'Tunte': '0:15:32',
            'Ayagaures': '0:12:06',
            'Meta Parque Sur': '0:07:09'
    }
    
    pacesNorm = pd.DataFrame(pd.Series(data, name='3')).T
    assert all(sample_results.pacesNorm.loc['3'] == pacesNorm)

def test_get_closestObjective(sample_results):
    # n=1 is 13:44:50, n=2 is 14:06:59, n=3 is 14:15:53
    assert sample_results.getClosestTimeToObjective('14:07:28') == '2'
    assert sample_results.getClosestTimeToObjective('14:05:21') == '2'
    assert sample_results.getClosestTimeToObjective('14:22:21') == '3'

def test_DNFsFilteredOut(sample_results):
    # Only 3 in results and not 4
    assert len(sample_results.times) == 3
