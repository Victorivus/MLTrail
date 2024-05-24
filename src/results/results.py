import pandas as pd
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class Results:
    def __init__(self, control_points: dict, times: pd.DataFrame, objective=0, offset=0,
                 clean_days=False, start_day=7, waves=False) -> None:
        self.control_points = control_points
        self.objective = objective
        self.times = times
        if (isinstance(clean_days, str) and clean_days == 'Auto') or\
                (isinstance(clean_days, bool) and clean_days):
            days = ['Lu.', 'Ma.', 'Me.', 'Je.', 'Ve.', 'Sa.', 'Di.']  # Weekdays abreviations in French
            days = [days[(start_day - 1 + j) % len(days)] for j in range(len(days))]
            self.times = self.clean_days(times, days)
        self.times = self.clean_times()
        self.set_offset(offset)
        self.times = self.times.apply(self._correct_times24h, axis=1)
        self.real_times = self.times
        self.waves = waves
        if self.waves:
            self.compute_real_times()
        self.time_deltas = self.get_time_deltas()
        self.distance_deltas = self.get_distance_deltas()
        self.paces = self.get_paces()
        self.paces_norm = self.get_paces_norm()

    def _correct_times24h(self, row) -> pd.Series:
        previous_time = row.iloc[0]
        adjusted_row = [row.iloc[0]]
        for time in row[1:]:
            if self.get_seconds(time) < self.get_seconds(previous_time):
                time = self.get_time(self.get_seconds(time) + 24 * 60 * 60)
            adjusted_row.append(time)
            previous_time = time
        return pd.Series(adjusted_row, index=row.index)

    def clean_days(self, times: pd.DataFrame, days: list[str]) -> pd.DataFrame:
        # Not tested
        times = times.apply(lambda x: x.map(lambda y: y[:9] if '\n' in y and len(y) > 9 else y))
        for i, day in enumerate(days):
            if (i + 1) == 1:
                times = times.apply(lambda x: x.map(lambda y: y[4:9] if f'\n{day}' in y else y))\
                             .apply(lambda x: x.map(lambda y: np.NaN if y == '.' or '.\n.' in y else
                                                            y.replace(f'{day} ', '') + ':00'))
            else:
                times = times.apply(lambda x: x.map(lambda y: self.format_time_over24h(
                    self.get_time(self.get_seconds(y.replace(f'{day} ', ''),
                                  offset=False) + i * 24 * 3600) if str(y).startswith(f'{day}') else y)))
        return times

    def clean_times(self, interpolate='previous') -> pd.DataFrame:
        # Filter out DNFs (last column is NaN)
        self.times = self.times.replace('', pd.NA)  # Some races instead of NaN, place an empty string
        self.times = self.times[(self.times.iloc[:, -1].isna() == False)]

        if interpolate == 'previous':
            self.times = self.times.ffill()  
        elif interpolate == 'next':
            self.times = self.times.bfill()
        elif interpolate == 'mean':
            # Not tested
            df_ffilled = self.times.ffill()
            df_ffilled = df_ffilled.applymap(self.get_seconds)
            df_bfilled = self.times.bfill()
            df_bfilled = df_bfilled.applymap(self.get_seconds)
            self.times = (df_ffilled + df_bfilled) / 2
            self.times = self.times.applymap(self.get_time)
            # raise NotImplementedError("This feature is not implemented yet.")
        return self.times

    def compute_real_times(self):
        first_cp_key, first_cp_value = list(self.control_points.items())[0]
        # self.real_times = 
        real_times = self.times.map(self.get_seconds)
        real_times = real_times.sub(real_times[first_cp_key], axis=0)
        self.real_times = real_times.map(self.get_time)
        return True

    def get_seconds(self, time: str, offset=True):
        d = 0  # days
        if 'day' in time:
            days, time = time.split(", ")
            d = int(days.split()[0])
        if len(time.split(':')) == 2:
            time += ':00'
        h, m, s = map(int, time.split(':'))
        if not offset:
            return d * 24 * 3600 + h * 3600 + m * 60 + s
        return d * 24 * 3600 + h * 3600 + m * 60 + s - self.offset

    def get_times(self) -> pd.DataFrame:
        '''
            Getter for times in hh:mm:ss since OFFICIAL departure time
        '''
        numeric_times = self.times.map(lambda x: self.get_seconds(x, offset=True))
        return numeric_times.map(self.get_time)

    def get_real_times(self) -> pd.DataFrame:
        '''
            Getter for real times: in hh:mm:ss since SELF departure if waves is True
            or get_times() if False
        '''
        if self.waves:
            return self.real_times
        else:
            return self.get_times()

    def get_hours(self) -> pd.DataFrame:
        '''
            Getter for times in hour of the day
        '''
        return self.times

    def get_time(self, seconds: int) -> str:
        '''
            Returns formated time in string from a number of seconds
        '''
        return str(dt.timedelta(seconds=(seconds))).split('.')[0]

    def get_allure(self, seconds, distance, offset=False):
        return self.get_time(self.get_seconds(seconds, offset=offset) / distance)

    def get_allure_norm(self, seconds, distance, D, offset=False):
        return self.get_allure(seconds, distance + D / 100, offset=offset)

    def total_time_to_delta(self, point_2, point_1):
        return self.get_time(self.get_seconds(point_2) - self.get_seconds(point_1))

    def td_to_string(self, x):
        ts = x.total_seconds()
        hours, remainder = divmod(ts, 3600)
        minutes, seconds = divmod(remainder, 60)
        if ts is None or pd.isna(ts):
            return str(np.nan)
        return ('{}:{:02d}:{:02d}').format(int(hours), int(minutes), int(seconds)) 

    @staticmethod
    def fix_format(df: pd.DataFrame) -> pd.DataFrame:
        return df.map(lambda x: str(x) + ':00')

    def plot_control_points(self, df, show_hours=False, xrotate=False, inverty=False, save_path=None):
        if show_hours:
            label_format = '%H:%M:%S'
        else:
            label_format = '%M:%S'

        fig, ax1 = plt.subplots(figsize=(12, 10), dpi=150)
        df = df.loc[:, ~(df == 'nan').all()]  # All column Nan is departure
        for i in df.reset_index()['index']:
            y = mdates.datestr2num(df.loc[i])
            ax1.plot(df.columns, y, marker='o', label=i)

        ax1.yaxis.set_major_formatter(mdates.DateFormatter(label_format))
        if inverty:
            ax1.invert_yaxis()
        if xrotate:
            plt.xticks(rotation=45)
        plt.ylabel("pace (min/km)")
        plt.legend(loc="best")
        if save_path is not None:
            plt.savefig(save_path)
        else:
            plt.show()

    def get_time_deltas(self):
        time_deltas = self.times.copy()
        prev_point = ''
        for point in self.control_points.keys():
            if prev_point == '':
                if self.control_points[point][0] > 0.0:
                    time_deltas[point] = self.times.apply(lambda x: self.total_time_to_delta(x[point], self.get_time(self.offset)), axis=1)
                else:
                    time_deltas[point] = self.times.apply(lambda x: None, axis=1)
            else:
                time_deltas[point] = self.times.apply(lambda x: self.total_time_to_delta(x[point], x[prev_point]), axis=1)
            prev_point = point
        return time_deltas

    def get_distance_deltas(self) -> dict:
        distance_deltas = {}
        prev_point = ''
        for point in self.control_points.keys():
            if prev_point == '':
                distance_deltas[point] = (self.control_points[point][0],
                                          self.control_points[point][1],
                                          self.control_points[point][2])
            else:
                distance_deltas[point] = (self.control_points[point][0] - self.control_points[prev_point][0],
                                          self.control_points[point][1] - self.control_points[prev_point][1],
                                          self.control_points[point][2] - self.control_points[prev_point][2])

            prev_point = point
        return distance_deltas

    def set_offset(self, offset):
        if isinstance(offset, int) and not isinstance(offset, bool):
            self.offset = offset
        elif isinstance(offset, str):
            self.offset = self.get_seconds(offset, offset=False)
        else:
            raise ValueError("offset must be departure time in 'hh:mm:ss'\
                              format or # seconds since midnight.")
        return True

    def get_paces(self):
        times_paces = self.times.copy()
        times_paces = times_paces[(times_paces.isna().any(axis=1) == False)]

        prev_point = ''
        for point in self.control_points.keys():
            if prev_point == '':
                if self.control_points[point][0] > 0.0:
                    times_paces['__all__' + point] = times_paces[point].map(lambda x: self.get_allure(x, self.control_points[point][0], offset=True))
                else:
                    times_paces['__all__' + point] = times_paces[point].map(lambda x: None)
            else:
                times_paces['__all__' + point] = times_paces.apply(lambda x: self.get_allure(
                    self.total_time_to_delta(x[point], x[prev_point]),
                    self.control_points[point][0] - self.control_points[prev_point][0]), axis=1)
            prev_point = point
        paces = times_paces[[col for col in times_paces.columns if col.startswith('__all__')]]
        paces.columns = [col.replace('__all__', '') for col in paces.columns]
        return paces

    def get_paces_norm(self):
        times_paces = self.times[(self.times[self.times.columns] != ':00')].copy()
        times_paces = times_paces[(times_paces.isna().any(axis=1) == False)]

        prev_point = ''
        for point in self.control_points.keys():
            if prev_point == '':
                if self.control_points[point][0] > 0.0:
                    times_paces['__allNorm__' + point] = times_paces[point].map(lambda x: self.get_allure_norm(x, self.control_points[point][0], self.control_points[point][1], offset=True))
                else:
                    times_paces['__allNorm__' + point] = times_paces[point].map(lambda x: None)
            else:
                times_paces['__allNorm__' + point] = times_paces.apply(lambda x: self.get_allure_norm(self.total_time_to_delta(x[point], x[prev_point]),
                                                                                        self.control_points[point][0] - self.control_points[prev_point][0],
                                                                                        self.control_points[point][1] - self.control_points[prev_point][1]
                                                                                        # + self.control_points[point][2]-self.control_points[prev_point][2]
                                                                                                      ), axis=1)
            prev_point = point

        paces_norm = times_paces[[col for col in times_paces.columns if col.startswith('__allNorm__')]]
        paces_norm.columns = [col.replace('__allNorm__', '') for col in paces_norm.columns]
        return paces_norm

    def get_stats(self, n1=4, n2=20, paces=None):
        if paces is None:
            paces = self.paces
        mean_n1 = pd.DataFrame(paces.head(n1).apply(lambda x: pd.to_timedelta(x)).mean().map(self.td_to_string)).T
        mean_n2 = pd.DataFrame(paces.head(n2).apply(lambda x: pd.to_timedelta(x)).mean().map(self.td_to_string)).T
        first = pd.DataFrame(paces.head(1).apply(lambda x: pd.to_timedelta(x)).min().map(self.td_to_string)).T 
        mins = pd.DataFrame(paces.apply(lambda x: pd.to_timedelta(x)).min().map(self.td_to_string)).T

        index = ['mins', 'first', f'mean_{n1}', f'mean_{n2}']

        means = pd.concat([mins, first, mean_n1, mean_n2], ignore_index=True)
        means['index'] = index
        means.set_index('index', inplace=True)
        return means

    def get_stats_norm(self, n1=4, n2=20):
        means = self.get_stats(n1=n1, n2=n2, paces=self.paces_norm)
        return means

    def set_objective(self, obj=0):
        self.objective = obj
        return

    def get_objective_times(self):
        return pd.DataFrame(self.times.iloc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(self.td_to_string)).T 

    def get_objective_paces(self):
        return pd.DataFrame(self.paces.iloc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(self.td_to_string)).T 

    def get_objective_paces_norm(self):
        return pd.DataFrame(self.paces_norm.iloc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(self.td_to_string)).T 

    def get_objective_mean_paces(self, n=5, paces=None):
        n = n - 1  # objective is already one of the n to compute mean on
        if paces is None:
            paces = self.paces
        # note: if n is impair, n-n/2 before objective and n/2 after it
        return pd.DataFrame(paces.iloc[self.objective - (n - n // 2):self.objective + n // 2]
                            .apply(lambda x: pd.to_timedelta(x)).mean().map(self.td_to_string)).T

    def get_objective_mean_times(self, n=5):
        return self.get_objective_mean_paces(n=n, paces=self.times)

    def get_objective_mean_paces_norm(self, n=5):
        return self.get_objective_mean_paces(n=n, paces=self.paces_norm)

    def get_closest_time_to_objective(self, time):
        # Compute absolute difference between each element in the DataFrame and X
        time = self.get_seconds(time, offset=False)
        closest_index = None
        min_diff = float('inf')  # Initialize with infinity
        # Iterate over each row in the DataFrame
        for index, row in self.times.iterrows():
            # Compute absolute difference between each element in the row and X
            diff = abs(self.get_seconds(row.iloc[-1]) - time)
            # Check if this row has the minimum difference seen so far
            if diff < min_diff:
                min_diff = diff
                closest_index = index
        self.objective = int(closest_index)

        return closest_index

    def format_time_over24h(self, td) -> str:
        '''
        Function to format timedelta to string in hours instead of default 1 day, ...
        '''
        total_seconds = self.get_seconds(td, offset=False)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
