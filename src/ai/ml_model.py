from abc import ABC, abstractmethod
import pandas as pd
from sklearn.model_selection import train_test_split
from ai.features import Features

# Abstract Model Class
class MLModel(ABC):
    def __init__(self, df: pd.DataFrame, target_column: str = 'time'):
        df[target_column] = df[target_column].apply(lambda x: Features.get_seconds(x))
        self.df = df
        self.target_column = target_column
        self.model = None
    
    @abstractmethod
    def train(self):
        pass
    
    @abstractmethod
    def predict(self, X):
        pass
    
    def split_data(self, test_size=0.2, random_state=42):
        X = self.df.drop(columns=[self.target_column])
        y = self.df[self.target_column]
        return train_test_split(X, y, test_size=test_size, random_state=random_state)

