import pandas as pd
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

class Results:
    def __init__(self, controlPoints, times, objective=0, offset=0, cleanDays=False, dayOne='Sa.', dayTwo='Di.'):
        self.controlPoints = controlPoints
        self.objective = objective
        self.offset = offset
        if isinstance(self.offset, str):
            self.offset = self.getSeconds(offset, offset=False)
        # For races over 24H we have two options in data:
        # They can have the Day added in front in some language, e.g. Sa. and Di. for Samedi and Dimanche
        # Or times go back to 00:00:00 with no extra information after 23:59:59
        if cleanDays:
            self.times = self.cleanDays(times, dayOne=dayOne, dayTwo=dayTwo)
        else:
            self.times = times
            self.times = self.cleanTimes()
            self.times = self.times.apply(self._correctTimes24h, axis=1)
        print(self.times.iloc[336]) 
        self.times = self.cleanTimes()
        self.timeDeltas = self.getTimeDeltas()
        self.distanceDeltas = self.getDistanceDeltas()
        self.paces = self.getPaces()
        self.pacesNorm = self.getPacesNorm()
    
    def _correctTimes24h(self,row):
        previous_time = row.iloc[0]
        adjusted_row = [row.iloc[0]]
        for time in row[1:]:
            if self.getSeconds(time) < self.getSeconds(previous_time):
                time = self.getTime(self.getSeconds(time) + 24*60*60)
            adjusted_row.append(time)
            previous_time = time
        return pd.Series(adjusted_row, index=row.index)
    
    def cleanDays(self, times, dayOne='Sa.', dayTwo='Di.'):
        times = times.apply(lambda x: x.map(lambda y: y[4:9] if f'\n{dayTwo}' in y else y))\
                                                .apply(lambda x: x.map(lambda y: y[4:9] if f'\n{dayOne}' in y else y))\
                                                .apply(lambda x: x.map(lambda y: np.NaN if y=='.' or '.\n.' in y else y.replace(f'{dayOne} ','')+':00'))\
                                                .apply(lambda x: x.map(lambda y: self.getTime(self.getSeconds(y.replace(f'{dayTwo} ',''), offset=False)+24*3600) if str(y).startswith(f'{dayTwo}') else y))
        return times

    def cleanTimes(self, interpolate='previous'):
        # Filter out DNFs (last column is NaN)
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
            #raise NotImplementedError("This feature is not implemented yet.")
        # print(times[(times.isna().any(axis=1) == True)])
        # print(times.count())
        return self.times
    
    def getSeconds(self, time, offset=True):
        #if np.isnan(time):
        #    time = '0:00:00'
        d = 0 # days
        if 'day' in time:
            days, time = time.split(", ")
            d = int(days.split()[0])
        if len(time.split(':'))==2:
            time+=':00'
        h, m, s = map(int, time.split(':'))
        if not offset:
            return d * 24 * 3600 + h * 3600 + m * 60 + s    
        return d * 24 * 3600 + h * 3600 + m * 60 + s - self.offset
    
    def getTime(self, seconds):
        return str(dt.timedelta(seconds=(seconds))).split('.')[0]

    def getAllure(self, seconds, distance):
        return self.getTime(self.getSeconds(seconds) / distance)

    def getAllureNorm(self, seconds, distance, D):
        return self.getAllure(seconds, distance + D/100)

    def totalTimeToDelta(self, point2, point1):
        return self.getTime(self.getSeconds(point2) - self.getSeconds(point1))

    def tdToString(self, x):
        ts = x.total_seconds()
        hours, remainder = divmod(ts, 3600)
        minutes, seconds = divmod(remainder, 60)
        return ('{}:{:02d}:{:02d}').format(int(hours), int(minutes), int(seconds)) 

    def fixFormat(self, df):
        return df.apply(lambda x: str(x)+':00')

    def plotControlPoints(self, df, showHours=False, xrotate=False, inverty=False):#,labels=True):
        if showHours:
            labelFormat = '%H:%M:%S'
        else:
            labelFormat = '%M:%S'
            
        #plt.figure(figsize=(8, 6), dpi=80)
        fig, ax1 = plt.subplots(figsize=(12, 10), dpi=80)
        for i in df.reset_index()['index']:
            y = mdates.datestr2num(df.loc[i])
            ax1.plot(df.columns, y, marker='o', label=i)
            #for j in df.columns:
            #    ax1.annotate(y, (j, y[j]))
            #    ax1.annotate(y[j], xy=(3, 1),  xycoords='data',
             #       xytext=(0.8, 0.95), textcoords='axes fraction',
              #      arrowprops=dict(facecolor='black', shrink=0.05),
               #     horizontalalignment='right', verticalalignment='top',
                #    )

        ax1.yaxis.set_major_formatter(mdates.DateFormatter(labelFormat))
        if inverty:
            ax1.invert_yaxis()
        if xrotate:
            plt.xticks(rotation=45)
        plt.legend(loc="best")
        plt.show()
        
    def getTimeDeltas(self):
        timeDeltas = self.times.copy()
        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint=='':
                #timeDeltas[point] = display(self.times[point].map(lambda x: self.getAllure(x, self.controlPoints[point][0]))
                timeDeltas[point] = self.times.apply(lambda x: self.totalTimeToDelta(x[point], self.getTime(self.offset)), axis=1)
            else:
                timeDeltas[point] = self.times.apply(lambda x: self.totalTimeToDelta(x[point], x[prevPoint]), axis=1)
            prevPoint = point
        return timeDeltas

    def getDistanceDeltas(self):
        distanceDeltas = {}
        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint=='':
                #timeDeltas[point] = display(self.times[point].map(lambda x: self.getAllure(x, self.controlPoints[point][0]))
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
        times_paces = self.times[(self.times[self.times.columns]!=':00')].copy()
        times_paces = times_paces[(times_paces.isna().any(axis=1) == False)]

        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint=='':
                times_paces['__all__'+point] = times_paces[point].map(lambda x: self.getAllure(x,self.controlPoints[point][0]))
            else:
                times_paces['__all__'+point] = times_paces.apply(lambda x: self.getAllure(self.totalTimeToDelta(x[point],x[prevPoint]),self.controlPoints[point][0]-self.controlPoints[prevPoint][0]),axis=1)
            prevPoint = point
        paces = times_paces[[col for col in times_paces.columns if col.startswith('__all__')]]
        paces.columns = [col.replace('__all__', '') for col in paces.columns]
        return paces

    def getPacesNorm(self):
        times_paces = self.times[(self.times[self.times.columns]!=':00')].copy()
        times_paces = times_paces[(times_paces.isna().any(axis=1) == False)]
        
        prevPoint = ''
        for point in self.controlPoints.keys():
            if prevPoint=='':
                times_paces['__allNorm__'+point] = times_paces[point].map(lambda x: self.getAllureNorm(x,self.controlPoints[point][0],self.controlPoints[point][1]))
            else:
                times_paces['__allNorm__'+point] = times_paces.apply(lambda x: self.getAllureNorm(self.totalTimeToDelta(x[point],x[prevPoint]),
                                                                                        self.controlPoints[point][0]-self.controlPoints[prevPoint][0],
                                                                                        self.controlPoints[point][1]-self.controlPoints[prevPoint][1]+
                                                                                            self.controlPoints[point][2]-self.controlPoints[prevPoint][2]
                                                                                        ),axis=1)
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
        means.set_index('index',inplace=True)
        return means
    
    def getStatsNorm(self, n1=4, n2=20):
        means = self.getStats(n1=n1, n2=n2, paces=self.pacesNorm)
        return means

    def setObjective(self, obj=0):
        self.objective = obj
        return

    def getObjectiveTimes(self):
        return pd.DataFrame(self.paces.loc[self.objective].apply(lambda x: pd.to_timedelta(x)).map(rs.tdToString)).T 

    def getObjectiveMeanTimes(self, n=4):
        # note: if n is impair, n-n/2 before objective and n/2 after it
        return pd.DataFrame(self.paces.loc[self.objective-(n-n//2):self.objective+n//2].apply(lambda x: pd.to_timedelta(x)).mean().map(self.tdToString)).T
