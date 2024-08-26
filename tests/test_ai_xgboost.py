import unittest
import pandas as pd
from sklearn.datasets import make_regression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from ai.xgboost import fit_cv, pipeline, XGBoostRegressorModel
from ai.ml_model import TargetNotSetError


SEED = 123456789

class TestMLModel(unittest.TestCase):
    def setUp(self):
        X, y = make_regression(n_samples=100, n_features=10, noise=0.1, random_state=SEED)
        self.df = pd.DataFrame(X, columns=['dist_segment', 'dist_total', 'target'] + [f'feature_{i}' for i in range(X.shape[1]-3)])
        self.df['target'] = y
        self.target_column = 'target'
        self.model = XGBoostRegressorModel(self.df, target_column=self.target_column)

    def test_fit_cv(self):
        X_train, X_test, y_train, y_test = train_test_split(self.df.drop(self.target_column, axis=1), self.df[self.target_column], test_size=0.3, random_state=SEED)
        param = {
            'regression__n_estimators': [10],
            'regression__learning_rate': [0.1]
        }
        regressor = ('xgboost', GradientBoostingRegressor(random_state=SEED))
        best_model = fit_cv(param, regressor, X_train, y_train, refit_score='r2')
        self.assertIsNotNone(best_model.best_estimator_)

    def test_pipeline(self):
        X_train, X_test, y_train, y_test = train_test_split(self.df.drop(self.target_column, axis=1), self.df[self.target_column], test_size=0.3, random_state=SEED)
        param = {
            'regression__n_estimators': [10],
            'regression__learning_rate': [0.1]
        }
        model = GradientBoostingRegressor(random_state=SEED)
        gcv = pipeline(model, X_train, y_train, param)
        self.assertIsNotNone(gcv.best_estimator_)

    def test_train_method(self):
        print('targeeet', self.model.target_column)
        self.model.train()
        self.assertIsNotNone(self.model.model)
        model_predict = XGBoostRegressorModel(self.df, target_column='')
        with self.assertRaises(TargetNotSetError):
            model_predict.train()


    def test_predict_method(self):
        X_test = self.df.drop(self.target_column, axis=1).sample(5, random_state=SEED)
        self.model.train()
        predictions = self.model.predict(X_test)
        self.assertEqual(predictions.shape[0], X_test.shape[0])

    def test_set_params(self):
        new_params = {
            'regression__max_depth': 2,
            'regression__subsample': 0.8
        }
        model_predict = XGBoostRegressorModel(self.df, target_column='')
        model_predict.set_params(new_params)
        self.assertEqual(model_predict.model.get_params()['regression__max_depth'], 2)
        self.assertEqual(model_predict.model.get_params()['regression__subsample'], 0.8)

if __name__ == '__main__':
    unittest.main()
