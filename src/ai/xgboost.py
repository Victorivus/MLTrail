import pandas as pd
from ai.features import Features
from ai.ml_model import MLModel
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error


# XGBoost Model Class for Regression
class XGBoostRegressorModel(MLModel):
    def __init__(self, df: pd.DataFrame, target_column: str):
        super().__init__(df, target_column)
        self.model = XGBRegressor(objective='reg:squarederror')
    
    def train(self):
        X_train, X_test, y_train, y_test = self.split_data()
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f'Mean Squared Error: {mse}')
        return mse
    
    def predict(self, X):
        return self.model.predict(X)
