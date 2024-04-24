import pandas as pd
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class Results:
    def __init__(self, controlPoints, times, objective=0, offset=0,
                 cleanDays=False, startDay=7) -> None:
        self.controlPoints = controlPoints
        self.objective = objective
        self.times = times
        if (isinstance(cleanDays, str) and cleanDays == 'Auto') or\
                (isinstance(cleanDays, bool) and cleanDays):
            days = ['Lu.', 'Ma.', 'Me.', 'Je.', 'Ve.', 'Sa.', 'Di.']  # Weekdays abreviations in French
            days = [days[(startDay - 1 + j) % len(days)] for j in range(len(days))]
            self.times = self.cleanDays(times, days)
        self.times = self.cleanTimes()
        if isinstance(offset, int):
            self.offset = offset
        elif isinstance(offset, str):
            self.offset = self.getSeconds(offset, offset=False)
        self.times = self.times.apply(self._correctTimes24h, axis=1)
        self.timeDeltas = self.getTimeDeltas()
        self.distanceDeltas = self.getDistanceDeltas()
        self.paces = self.getPaces()
        self.pacesNorm = self.getPacesNorm()
    
    def _correctTimes24h(self, row):
        previous_time = row.iloc[0]
        adjusted_row = [row.iloc[0]]
        for time in row[1:]:
            if self.getSeconds(time) < self.getSeconds(previous_time):
                time = self.getTime(self.getSeconds(time) + 24*60*60)
            adjusted_row.append(time)
            previous_time = time
        return pd.Series(adjusted_row, index=row.index)
    
    def cleanDays(self, times, days):
        # Not tested
        for i, day in enumerate(days):
            if (i+1) == 1:
                times.apply(lambda x: x.map(lambda y: y[4:9] if f'\n{day}' in y else y))\
                     .apply(lambda x: x.map(lambda y: np.NaN if y == '.' or '.\n.' in y else y.replace(f'{day} ', '')+':00'))
            else:
                times.apply(lambda x: x.map(lambda y: self.getTime(self.getSeconds(y.replace(f'{day} ', ''), offset=False)+i*24*3600) if str(y).startswith(f'{day}') else y))       
        return times

    def cleanTimes(self, interpolate='previous'):
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
            df_ffilled = df_ffilled.applymap(self.getSeconds)
            df_bfilled = self.times.bfill()
            df_bfilled = df_bfilled.applymap(self.getSeconds)
            self.times = (df_ffilled + df_bfilled) / 2
            self.times = self.times.applymap(self.getTime)
            # raise NotImplementedError("This feature is not implemented yet.")
        return self.times

    def getSeconds(self, time, offset=True):
        # if np.isnan(time):
        #    time = '0:00:00'
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

    def getTime(self, seconds):
        return str(dt.timedelta(seconds=(seconds))).split('.')[0]

    def getAllure(self, seconds, distance, offset=False):
        return self.getTime(self.getSeconds(seconds, offset=offset) / distance)

    def getAllureNorm(self, seconds, distance, D, offset=False):
        return self.getAllure(seconds, distance + D/100, offset=offset)

    def totalTimeToDelta(self, point2, point1):
        return self.getTime(self.getSeconds(point2) - self.getSeconds(point1))

    def tdToString(self, x):
        ts = x.total_seconds()
        hours, remainder = divmod(ts, 3600)
        minutes, seconds = divmod(remainder, 60)
        return ('{}:{:02d}:{:02d}').format(int(hours), int(minutes), int(seconds)) 

    def fixFormat(self, df):
        return df.apply(lambda x: str(x)+':00')

    def plotControlPoints(self, df, showHours=False, xrotate=False, inverty=False, savePath=None):  # ,labels=True):
        if showHours:
            labelFormat = '%H:%M:%S'
        else:
            labelFormat = '%M:%S'

        # plt.figure(figsize=(8, 6), dpi=80)
        fig, ax1 = plt.subplots(figsize=(12, 10), dpi=150)
        for i in df.reset_index()['index']:
            y = mdates.datestr2num(df.loc[i])
            ax1.plot(df.columns, y, marker='o', label=i)
            # for j in df.columns:
            #    ax1.annotate(y, (j, y[j]))
            #    ax1.annotate(y[j], xy=(3, 1),  xycoords='data',
            #       xytext=(0.8, 0.95), textcoords='axes fraction',
            #         arrowprops=dict(facecolor='black', shrink=0.05),
            #        horizontalalignment='right', verticalalignment='top',
            #         )

        ax1.yaxis.set_major_formatter(mdates.DateFormatter(labelFormat))
        if inverty:
            ax1.invert_yaxis()
        if xrotate:
            plt.xticks(rotation=45)
        plt.ylabel("pace (min/km)")
        plt.legend(loc="best")
        if savePath is not None:
            plt.savefig(savePath)
        else:
            plt.show()
        
    def getTimeDeltas(self):
        timeDeltas = self.times.copy()
        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint == '':
                # timeDeltas[point] = display(self.times[point].map(lambda x: self.getAllure(x, self.controlPoints[point][0]))
                timeDeltas[point] = self.times.apply(lambda x: self.totalTimeToDelta(x[point], self.getTime(self.offset)), axis=1)
            else:
                timeDeltas[point] = self.times.apply(lambda x: self.totalTimeToDelta(x[point], x[prevPoint]), axis=1)
            prevPoint = point
        return timeDeltas

    def getDistanceDeltas(self) -> dict:
        distanceDeltas = {}
        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint == '':
                # timeDeltas[point] = display(self.times[point].map(lambda x: self.getAllure(x, self.controlPoints[point][0]))
                distanceDeltas[point] = (self.controlPoints[point][0],
                                         self.controlPoints[point][1],
                                         self.controlPoints[point][2])
            else:
                distanceDeltas[point] = (self.controlPoints[point][0] - self.controlPoints[prevPoint][0],
                                         self.controlPoints[point][1] - self.controlPoints[prevPoint][1],
                                         self.controlPoints[point][2] - self.controlPoints[prevPoint][2])
                                        
            prevPoint = point
        return distanceDeltas

    def setOffset(self, offset):
        self.offset = offset
        return True
    
    def getPaces(self):
        # times_paces = self.times[(self.times[self.times.columns]!=':00')].copy()
        times_paces = self.times.copy()
        times_paces = times_paces[(times_paces.isna().any(axis=1) == False)]

        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint == '':
                times_paces['__all__'+point] = times_paces[point].map(lambda x: self.getAllure(x, self.controlPoints[point][0], offset=True))
            else:
                times_paces['__all__'+point] = times_paces.apply(lambda x: self.getAllure(self.totalTimeToDelta(x[point], x[prevPoint]), self.controlPoints[point][0]-self.controlPoints[prevPoint][0]), axis=1)
            prevPoint = point
        paces = times_paces[[col for col in times_paces.columns if col.startswith('__all__')]]
        paces.columns = [col.replace('__all__', '') for col in paces.columns]
        return paces

    def getPacesNorm(self):
        times_paces = self.times[(self.times[self.times.columns] != ':00')].copy()
        times_paces = times_paces[(times_paces.isna().any(axis=1) == False)]
        
        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint == '':
                times_paces['__allNorm__'+point] = times_paces[point].map(lambda x: self.getAllureNorm(x, self.controlPoints[point][0], self.controlPoints[point][1], offset=True))
            else:
                times_paces['__allNorm__'+point] = times_paces.apply(lambda x: self.getAllureNorm(self.totalTimeToDelta(x[point], x[prevPoint]),
                                                                                        self.controlPoints[point][0]-self.controlPoints[prevPoint][0],
                                                                                        self.controlPoints[point][1]-self.controlPoints[prevPoint][1] +
                                                                                            self.controlPoints[point][2]-self.controlPoints[prevPoint][2]
                                                                                                  ), axis=1)
            prevPoint = point

        paces_norm = times_paces[[col for col in times_paces.columns if col.startswith('__allNorm__')]]
        paces_norm.columns = [col.replace('__allNorm__', '') for col in paces_norm.columns]
        return paces_norm

    def getStats(self, n1=4, n2=20, paces=None):
        if paces is None:
            paces = self.paces
        mean_n1 = pd.DataFrame(paces.head(n1).apply(lambda x: pd.to_timedelta(x)).mean().map(self.tdToString)).T
        mean_n2 = pd.DataFrame(paces.head(n2).apply(lambda x: pd.to_timedelta(x)).mean().map(self.tdToString)).T
        first = pd.DataFrame(paces.head(1).apply(lambda x: pd.to_timedelta(x)).min().map(self.tdToString)).T 
        mins = pd.DataFrame(paces.apply(lambda x: pd.to_timedelta(x)).min().map(self.tdToString)).T

        index = ['mins', 'first', f'mean_{n1}', f'mean_{n2}']

        means = pd.concat([mins, first, mean_n1, mean_n2], ignore_index=True)
        means['index'] = index
        means.set_index('index', inplace=True)
        return means
    
    def getStatsNorm(self, n1=4, n2=20):
        means = self.getStats(n1=n1, n2=n2, paces=self.pacesNorm)
        return means

    def setObjective(self, obj=0):
        self.objective = obj
        return

    def getObjectiveTimes(self):
        return pd.DataFrame(self.times.iloc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(self.tdToString)).T 

    def getObjectivePaces(self):
        return pd.DataFrame(self.paces.iloc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(self.tdToString)).T 

    def getObjectivePacesNorm(self):
        return pd.DataFrame(self.pacesNorm.iloc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(self.tdToString)).T 

    def getObjectiveMeanPaces(self, n=5, paces=None):
        n = n-1  # objective is already one of the n to compute mean on
        if paces is None:
            paces = self.paces
        # note: if n is impair, n-n/2 before objective and n/2 after it
        return pd.DataFrame(paces.iloc[self.objective-(n-n//2):self.objective+n//2]\
                            .apply(lambda x: pd.to_timedelta(x)).mean().map(self.tdToString)).T

    def getObjectiveMeanTimes(self, n=5):
        return self.getObjectiveMeanPaces(n=n, paces=self.times)
    
    def getObjectiveMeanPacesNorm(self, n=5):
        return self.getObjectiveMeanPaces(n=n, paces=self.pacesNorm)

    def getClosestTimeToObjective(self, time):
        # Compute absolute difference between each element in the DataFrame and X
        # diff = (self.getSeconds() - self.getSeconds(time)).abs()
        time = self.getSeconds(time, offset=False)
        closest_index = None
        min_diff = float('inf')  # Initialize with infinity
        # Iterate over each row in the DataFrame
        for index, row in self.times.iterrows():
            # Compute absolute difference between each element in the row and X
            diff = abs(self.getSeconds(row.iloc[-1]) - time)

            # Check if this row has the minimum difference seen so far
            if diff < min_diff:
                min_diff = diff
                closest_index = index
        self.objective = int(closest_index)

        return closest_index
    
    # Function to format timedelta to string in hours instead of default 1 day, ...
    def formatTimeOver24h(self, td):
        total_seconds = self.getSeconds(td, offset=False)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
