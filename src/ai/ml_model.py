from abc import ABC, abstractmethod
import pandas as pd
from sklearn.model_selection import train_test_split
from ai.features import Features
import sqlite3


# Abstract Model Class
class MLModel(ABC):
    def __init__(self, df: pd.DataFrame, target_column: str = 'time', only_partials=True):
        if only_partials:
            # This improves accuracy and performance of models. The total may be computed
            # as a sum of all the partials (races below 30km are more similar to partials)
            df = df[(df['dist_segment']!=df['dist_total']) & (df['dist_segment']<30)]
        self.df = df.copy()
        if pd.api.types.is_string_dtype(df[target_column]):
            self.df[target_column] = self.df[target_column].apply(lambda x: Features.get_seconds(x))
        self.target_column = target_column
        self.model = None

    @abstractmethod
    def train(self):
        pass

    @abstractmethod
    def predict(self, X):
        pass

    def split_data(self, test_size=0.2, random_state=42):
        """
        Splits the data into training and testing sets.
        """
        X = self.df.drop(columns=[self.target_column])
        y = self.df[self.target_column]
        return train_test_split(X, y, test_size=test_size, random_state=random_state)

    @staticmethod
    def format_time(seconds: int) -> str:
        """
        Formats seconds into a time string.
        """
        return Features.format_time(seconds)

    def save_model_params(self, params: dict, db_path: str = 'models.db'):
        """
        Saves the model parameters to a database.
        """
        # TODO: not implemented
        raise NotImplementedError
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_params (
                    model_name TEXT,
                    param_name TEXT,
                    param_value TEXT
                )
            ''')

            for param_name, param_value in params.items():
                cursor.execute('''
                    INSERT INTO model_params (model_name, param_name, param_value)
                    VALUES (?, ?, ?)
                ''', (self.__class__.__name__, param_name, str(param_value)))

            conn.commit()

        except sqlite3.Error as e:
            print(f"Error saving model parameters to database: {e}")

        finally:
            if conn:
                conn.close()

    def load_model_params(self, db_path: str = 'models.db'):
        """
        Loads model parameters from the database.
        """
        # TODO: not implemented
        raise NotImplementedError
        params = {}
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT param_name, param_value 
                FROM model_params
                WHERE model_name = ?
            ''', (self.__class__.__name__,))

            rows = cursor.fetchall()
            for param_name, param_value in rows:
                params[param_name] = param_value

            print(f"Loaded parameters for {self.__class__.__name__}: {params}")

        except sqlite3.Error as e:
            print(f"Error loading model parameters from database: {e}")

        finally:
            if conn:
                conn.close()

        return params
