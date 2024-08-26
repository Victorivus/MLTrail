import warnings
import pandas as pd
from xgboost import XGBRegressor
from sklearn.metrics import (explained_variance_score, max_error, mean_absolute_error, 
                             mean_squared_error, r2_score, make_scorer)
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.exceptions import DataConversionWarning
from imblearn.pipeline import Pipeline as ImbPipeline
from ai.ml_model import MLModel

# Suppress warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=DataConversionWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")

# Constants for reproducibility and configuration
SEED = 123456789
CV_FOLDS = 3

def fit_cv(param, regressor, X_train, y_train, score=None, refit_score='mean_squared_error'):
    """
    Fits a model using cross-validation and returns the best estimator.
    """
    if score is None:
        score = {'r2': make_scorer(r2_score)}

    print(f"Working on {regressor[0]}...")
    best_model = imb_pipeline(regressor[1], X_train, y_train, param, score, refit_score)

    print(f"Best parameter for {regressor[0]} is {best_model.best_params_}")
    print(f"Best score for {regressor[0]} is {best_model.best_score_}")
    print('-' * 50)
    print('\n')

    return best_model

def imb_pipeline(model, X, y, params, score=None, refit_score='accuracy_score', cv=CV_FOLDS):
    """
    Sets up a pipeline with scaling and regression, and performs grid search cross-validation.
    """
    if score is None:
        score = {"accuracy_score": "accuracy"}

    pipeline = ImbPipeline([
        ('minmax_scaler', MinMaxScaler()), # Use one scaler at a time, selected in params grid
        ('std_scaler', StandardScaler()),
        ('regression', model)
    ])

    gcv = GridSearchCV(estimator=pipeline, param_grid=params, cv=cv, scoring=score, n_jobs=-1,
                       refit=refit_score, return_train_score=False, verbose=1)
    gcv.fit(X, y)
    
    return gcv

class XGBoostRegressorModel(MLModel):
    parameters = {
        "std_scaler": ["passthrough"],  # skip this step
        "regression__min_samples_split": [2, 3, 4],
        "regression__min_samples_leaf": [2, 5, 8],
        "regression__max_depth": [2, 6],
        "regression__criterion": ["friedman_mse"],  # Default value of ‘friedman_mse’ is generally the best
        "regression__subsample": [0.8, 1.0],
        "regression__n_estimators": [150, 300]
    }

    score = {
        'explained_variance': make_scorer(explained_variance_score), 
        'max_error': make_scorer(max_error),
        'mean_absolute_error': make_scorer(mean_absolute_error), 
        'mean_squared_error': make_scorer(mean_squared_error),
        'r2': make_scorer(r2_score)
    }

    def __init__(self, df: pd.DataFrame, target_column: str):
        super().__init__(df, target_column)
        self.model = ('xgboost', GradientBoostingRegressor(random_state=SEED))
    
    def train(self):
        """
        Trains the model using the training data and prints the Mean Squared Error.
        """
        X_train, X_test, y_train, y_test = self.split_data()
        self.model = fit_cv(param=self.parameters, regressor=self.model, X_train=X_train,
                            y_train=y_train, score=self.score).best_estimator_

        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f'Mean Squared Error: {mse}')
        return mse
    
    def predict(self, X, format='seconds'):
        """
        Makes predictions on the input data X.

        Args:
            X (pandas.DataFrame): Data from the races. It must have the same structure as the training data.
            format (str): if equal to 'time', the returned object will have predictions in str format and not in seconds (int).

        Returns:
            pandas.Series: Model's prediction from X.
        """
        if self.target_column in X.columns:
            print(f'Dropping {self.target_column} from data...')
            X = X.drop(self.target_column, axis='columns')
        if format == 'time':
            return pd.Series([self.format_time(x) for x in self.model.predict(X)],
                             name='PREDICTION')
        return self.model.predict(X)
