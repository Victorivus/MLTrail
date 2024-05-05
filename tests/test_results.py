'''
Test module for the Results class
'''
import os
import unittest
import pytest
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta
from results.results import Results
from tools import get_untested_functions


class TestResults():
    def tearDown(self):
        plt.close()

    # Define a fixture for a sample instance of the Results class
    @staticmethod
    @pytest.fixture
    def sample_results() -> Results:
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
        race_info = {'date': '2024-02-24', 'tz': '0', 'hd': '00:00:03', 'jd': '6'}
        return Results(control_points, times, offset=race_info['hd'], clean_days=False, start_day=race_info['jd'])


    # Test case for getData method
    def test___init__(self, sample_results):
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
        assert all(sample_results.times.loc['3'] == times)


    # Test case for paces computation
    def test_get_paces(self, sample_results):
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
    def test_get_paces_norm(self, sample_results):
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

        paces_norm = pd.DataFrame(pd.Series(data, name='3')).T
        assert all(sample_results.paces_norm.loc['3'] == paces_norm)

    def test_get_closest_time_to_objective(self, sample_results):
        # n=1 is 13:44:50, n=2 is 14:06:59, n=3 is 14:15:53
        assert sample_results.get_closest_time_to_objective('14:07:28') == '2'
        assert sample_results.get_closest_time_to_objective('14:05:21') == '2'
        assert sample_results.get_closest_time_to_objective('14:22:21') == '3'

    def test_DNFs_filtered_out(self, sample_results):
        # Only 3 in results and not 4
        assert len(sample_results.times) == 3

    def test_get_stats(self, sample_results):
        data = {
            'Tenoya': ['0:04:19', '0:04:28', '0:04:24', '0:04:24'],
            'Arucas': ['0:05:31', '0:05:40', '0:05:34', '0:05:34'],
            'Teror': ['0:06:01', '0:06:02', '0:06:04', '0:06:04'],
            'Fontanales': ['0:07:01', '0:07:03', '0:07:02', '0:07:02'],
            'El Hornillo': ['0:06:56', '0:07:25', '0:07:15', '0:07:15'],
            'Artenara': ['0:07:15', '0:07:38', '0:07:25', '0:07:25'],
            'Tejeda': ['0:06:36', '0:06:36', '0:06:53', '0:06:53'],
            'Roque Nublo': ['0:08:38', '0:08:53', '0:09:08', '0:09:08'],
            'Garañon': ['0:06:51', '0:06:51', '0:08:05', '0:08:05'],
            'Tunte': ['0:05:44', '0:05:44', '0:05:56', '0:05:56'],
            'Ayagaures': ['0:05:30', '0:05:30', '0:05:57', '0:05:57'],
            'Meta Parque Sur': ['0:04:58', '0:04:58', '0:05:20', '0:05:20']
        }
        df = pd.DataFrame(data, index=['mins', 'first', 'mean_4', 'mean_20'])
        assert all(df == sample_results.get_stats()), "Function get_stats failed."

    def test_get_stats_norm(self, sample_results):
        data = {
            'mins': ['0:03:19', '0:05:07', '0:04:40', '0:05:10', '0:09:17', '0:05:28',
                     '0:07:31', '0:04:44', '0:08:50', '0:14:34', '0:10:28', '0:06:09'],
            'first': ['0:03:25', '0:05:16', '0:04:40', '0:05:12', '0:09:56', '0:05:45',
                      '0:07:31', '0:04:52', '0:08:50', '0:14:34', '0:10:28', '0:06:09'],
            'mean_4': ['0:03:22', '0:05:10', '0:04:42', '0:05:10', '0:09:43', '0:05:36',
                       '0:07:50', '0:05:00', '0:10:26', '0:15:06', '0:11:19', '0:06:36'],
            'mean_20': ['0:03:22', '0:05:10', '0:04:42', '0:05:10', '0:09:43', '0:05:36',
                        '0:07:50', '0:05:00', '0:10:26', '0:15:06', '0:11:19', '0:06:36']
        }
        sn = pd.DataFrame(data).T
        sn.columns = list(sample_results.control_points.keys())
        assert all(sn == sample_results.get_stats_norm()), "Function get_stats_norm failed."

    def test_get_distance_deltas(self, sample_results):
        dd = {'Tenoya': (11.43, 348, -188),
              'Arucas': (8.010000000000002, 356, -294),
              'Teror': (12.509999999999998, 805, -440),
              'Fontanales': (11.599999999999998, 954, -539),
              'El Hornillo': (9.96, 626, -878),
              'Artenara': (13.600000000000001, 1067, -622),
              'Tejeda': (12.519999999999996, 763, -917),
              'Roque Nublo': (8.52000000000001, 950, -250),
              'Garañon': (3.1699999999999875, 173, -244),
              'Tunte': (12.940000000000012, 327, -1111),
              'Ayagaures': (12.309999999999988, 434, -1017),
              'Meta Parque Sur': (14.170000000000016, 197, -470)}
        assert dd == sample_results.get_distance_deltas()

    def test_get_objective_paces(self, sample_results):
        data = {
            'Tenoya': ['0:04:28'],
            'Arucas': ['0:05:40'],
            'Teror': ['0:06:02'],
            'Fontanales': ['0:07:03'],
            'El Hornillo': ['0:07:25'],
            'Artenara': ['0:07:38'],
            'Tejeda': ['0:06:36'],
            'Roque Nublo': ['0:08:53'],
            'Garañon': ['0:06:51'],
            'Tunte': ['0:05:44'],
            'Ayagaures': ['0:05:30'],
            'Meta Parque Sur': ['0:04:58']
        }
        op = pd.DataFrame(data, index=['1'])
        assert all(op == sample_results.get_objective_paces())

    def test_get_objective_paces_norm(self, sample_results):
        data = {
            'Tenoya': ['0:03:25'],
            'Arucas': ['0:05:16'],
            'Teror': ['0:04:40'],
            'Fontanales': ['0:05:12'],
            'El Hornillo': ['0:09:56'],
            'Artenara': ['0:05:45'],
            'Tejeda': ['0:07:31'],
            'Roque Nublo': ['0:04:52'],
            'Garañon': ['0:08:50'],
            'Tunte': ['0:14:34'],
            'Ayagaures': ['0:10:28'],
            'Meta Parque Sur': ['0:06:09']
        }
        opn = pd.DataFrame(data, index=['1'])
        assert all(opn == sample_results.get_objective_paces_norm())

    def test_get_objective_mean_paces_norm(self, sample_results):
        data = {
            'Tenoya': ['0:03:25'],
            'Arucas': ['0:05:16'],
            'Teror': ['0:04:40'],
            'Fontanales': ['0:05:12'],
            'El Hornillo': ['0:09:56'],
            'Artenara': ['0:05:45'],
            'Tejeda': ['0:07:31'],
            'Roque Nublo': ['0:04:52'],
            'Garañon': ['0:08:50'],
            'Tunte': ['0:14:34'],
            'Ayagaures': ['0:10:28'],
            'Meta Parque Sur': ['0:06:09']
        }
        ompn = pd.DataFrame(data)
        assert all(ompn == sample_results.get_objective_mean_paces_norm())

    def test_get_objective_mean_paces(self, sample_results):
        data = {
            'Tenoya': ['0:04:26'],
            'Arucas': ['0:05:33'],
            'Teror': ['0:06:11'],
            'Fontanales': ['0:07:02'],
            'El Hornillo': ['0:07:26'],
            'Artenara': ['0:07:24'],
            'Tejeda': ['0:06:59'],
            'Roque Nublo': ['0:08:38'],
            'Garañon': ['0:09:32'],
            'Tunte': ['0:05:59'],
            'Ayagaures': ['0:06:00'],
            'Meta Parque Sur': ['0:05:16']
        }
        omp = pd.DataFrame(data)
        assert all(omp == sample_results.get_objective_mean_paces())

    def test_get_objective_times(self, sample_results):
        data = {
            'Tenoya': ['0:51:13'],
            'Arucas': ['1:36:42'],
            'Teror': ['2:52:18'],
            'Fontanales': ['4:14:16'],
            'El Hornillo': ['5:28:13'],
            'Artenara': ['7:12:03'],
            'Tejeda': ['8:34:43'],
            'Roque Nublo': ['9:50:27'],
            'Garañon': ['10:12:13'],
            'Tunte': ['11:26:32'],
            'Ayagaures': ['12:34:22'],
            'Meta Parque Sur': ['13:44:50']
        }
        ot = pd.DataFrame(data, index=['1'])
        assert all(ot == sample_results.get_objective_times())

    def test_get_objective_mean_times(self, sample_results):
        data = {
            'Tenoya': ['0:50:46'],
            'Arucas': ['1:35:19'],
            'Teror': ['2:52:42'],
            'Fontanales': ['4:14:19'],
            'El Hornillo': ['5:28:31'],
            'Artenara': ['7:09:21'],
            'Tejeda': ['8:36:47'],
            'Roque Nublo': ['9:50:27'],
            'Garañon': ['10:20:43'],
            'Tunte': ['11:38:20'],
            'Ayagaures': ['12:52:21'],
            'Meta Parque Sur': ['14:06:59']
        }
        omt = pd.DataFrame(data)
        assert all(omt == sample_results.get_objective_mean_times())

    def test_get_time_deltas(self, sample_results):
        data = {
            '1': ['0:51:10', '0:45:29', '1:15:36', '1:21:58', '1:13:57', '1:43:50',
                  '1:22:40', '1:15:44', '0:21:46', '1:14:19', '1:07:50', '1:10:28'],
            '2': ['0:50:43', '0:44:33', '1:17:23', '1:21:37', '1:14:12', '1:40:50',
                  '1:27:26', '1:13:40', '0:30:16', '1:17:37', '1:14:01', '1:14:38'],
            '3': ['0:49:31', '0:44:14', '1:15:25', '1:21:27', '1:09:07', '1:38:43',
                  '1:28:31', '1:24:17', '0:25:02', '1:19:18', '1:18:25', '1:21:50']
        }
        td = pd.DataFrame(data).T
        td.columns = list(sample_results.control_points.keys())
        assert all(td == sample_results.get_time_deltas())

    def test_clean_times(self, sample_results):
        # TODO --> This method is not sufficiently tested...
        data = {
            '1': ['00:51:13', '01:36:42', '02:52:18', '04:14:16', '05:28:13', '07:12:03',
                  '08:34:43', '09:50:27', '10:12:13', '11:26:32', '12:34:22', '13:44:50'],
            '2': ['00:50:46', '01:35:19', '02:52:42', '04:14:19', '05:28:31', '07:09:21',
                  '08:36:47', '09:50:27', '10:20:43', '11:38:20', '12:52:21', '14:06:59'],
            '3': ['00:49:34', '01:33:48', '02:49:13', '04:10:40', '05:19:47', '06:58:30',
                  '08:27:01', '09:51:18', '10:16:20', '11:35:38', '12:54:03', '14:15:53']
        }
        ct = pd.DataFrame(data).T
        ct.columns = list(sample_results.control_points.keys())
        assert all(ct == sample_results.clean_times())

    def test_get_seconds(self, sample_results):
        assert sample_results.get_seconds('1:30:00') == 5397
        assert sample_results.get_seconds('1:30:00', offset=False) == 5400

    def test_total_time_to_delta(self, sample_results):
        assert sample_results.total_time_to_delta('2:37:23', '1:00:00') == '1:37:23'

    def test_td_to_string(self, sample_results):
        assert sample_results.td_to_string(timedelta(hours=1)) == '1:00:00'
        assert sample_results.td_to_string(timedelta(hours=2,
                                                     minutes=47,
                                                     seconds=2)) == '2:47:02'

    def test_set_objective(self, sample_results):
        sample_results.set_objective(100)
        assert sample_results.objective == 100

    def test_get_allure(self, sample_results):
        assert sample_results.get_allure('1:00:00', 10) == '0:06:00'  # 6min/km
        assert sample_results.get_allure('0:35:00', 10) == '0:03:30'  # 3'30"/km

    def test_get_allure_norm(self, sample_results):
        assert sample_results.get_allure_norm('1:00:00', 10, 500) == '0:04:00'  # 4min/km-effort
        assert sample_results.get_allure_norm('4:30:00', 42.195, 2700) == '0:03:54'  # 6'23"/km-effort

    def test_fix_format(self, sample_results):
        df: pd.DataFrame = Results.fix_format(pd.DataFrame({'A': ['1:00', '2:00', '3:00'], 'B': ['4:00', '5:00', '6:00']}))
        assert df.equals(pd.DataFrame({'A': ['1:00:00', '2:00:00', '3:00:00'], 'B': ['4:00:00', '5:00:00', '6:00:00']}))

    def test_set_offset(self, sample_results):
        # Test with integer input
        assert sample_results.set_offset(3600)
        assert sample_results.offset == 3600

        # Test with string input
        assert sample_results.set_offset('01:00:00')
        assert sample_results.offset == 3600

        # Test with invalid input
        with pytest.raises(ValueError):
            sample_results.set_offset(True)

        # Test with invalid input
        with pytest.raises(ValueError):
            sample_results.set_offset('invalid time')

    def test_format_time_over24h(self, sample_results):
        # Test case with timedelta less than 24 hours
        td_less_than_24h = str(timedelta(hours=10, minutes=30, seconds=45))
        expected_result_less_than_24h = "10:30:45"
        assert sample_results.format_time_over24h(td_less_than_24h) == expected_result_less_than_24h

        # Test case with timedelta more than 24 hours
        td_more_than_24h = str(timedelta(days=2, hours=15, minutes=45, seconds=20))
        expected_result_more_than_24h = "63:45:20"
        assert sample_results.format_time_over24h(td_more_than_24h) == expected_result_more_than_24h

    def test_get_time(self, sample_results):
        # Test case with seconds less than one hour
        seconds_less_than_hour = 3600  # 1 hour
        expected_result_less_than_hour = "1:00:00"
        assert sample_results.get_time(seconds_less_than_hour) == expected_result_less_than_hour

        # Test case with seconds more than one hour
        seconds_more_than_hour = 9920  # 2 hours 45 minutes and 20 seconds
        expected_result_more_than_hour = "2:45:20"
        assert sample_results.get_time(seconds_more_than_hour) == expected_result_more_than_hour

    def test_clean_days(self, sample_results):
        # Create a sample DataFrame for testing
        data = {
            'Tenoya': ['Ve. 23:51', 'Ve. 23:50', 'Ve. 23:49'],
            'Arucas': ['Sa. 01:36', 'Sa. 01:35\nSa.01:37', 'Sa. 01:33'],
            'Teror': ['Sa. 02:52', 'Sa. 02:52', 'Sa. 02:49']
        }
        df = pd.DataFrame(data)

        # Define the expected cleaned DataFrame
        expected_data = {
            'Tenoya': ['23:51:00', '23:50:00', '23:49:00'],
            'Arucas': ['25:36:00', '25:35:00', '25:33:00'],
            'Teror': ['26:52:00', '26:52:00', '26:49:00']
        }
        expected_df = pd.DataFrame(expected_data)

        # Define sample days list
        days = ['Ve.', 'Sa.']

        # Clean the DataFrame
        cleaned_df = sample_results.clean_days(df, days)

        # Check if the cleaned DataFrame matches the expected DataFrame
        assert cleaned_df.equals(expected_df)

##########################################################################################
#
#       Plot tests
#
##########################################################################################


    def test_plot_control_points(self, sample_results):
        plot_path = "test_plot_control_points_default.png"
        sample_results.plot_control_points(sample_results.get_stats(), showHours=False, xrotate=False, inverty=False, savePath=plot_path)
        assert os.path.exists(plot_path)
        os.remove(plot_path)

    def test_plot_control_points_show_hours(self, sample_results):
        plot_path = "test_plot_control_points_show_hours.png"
        sample_results.plot_control_points(sample_results.get_stats(), showHours=True, xrotate=False, inverty=False, savePath=plot_path)
        assert os.path.exists(plot_path)
        os.remove(plot_path)

    def test_plot_control_points_xrotate(self, sample_results):
        plot_path = "test_plot_control_points_xrotate.png"
        sample_results.plot_control_points(sample_results.get_stats(), showHours=False, xrotate=True, inverty=False, savePath=plot_path)
        assert os.path.exists(plot_path)
        os.remove(plot_path)

    def test_plot_control_points_inverty(self, sample_results):
        plot_path = "test_plot_control_points_inverty.png"
        sample_results.plot_control_points(sample_results.get_stats(), showHours=False, xrotate=False, inverty=True, savePath=plot_path)
        assert os.path.exists(plot_path)
        os.remove(plot_path)

    def test_implemented_tests(self):
        unused_functions = get_untested_functions(Results, TestResults)
        assert len(unused_functions) == 0, "Results is not tested enough. pytest -s for details."
        # if len(unused_functions) > 0:
        #   print("untested functions from Results:")
        #   print(unused_functions)
        #   warnings.warn(f"{len(unused_functions)} functions from Results class not tested.")

if __name__ == '__main__':
    unittest.main()