"""Tests for the background training service."""
import time
import unittest
from unittest.mock import patch, MagicMock
from ai.training_service import TrainingState, TrainingStatus, start_background_training, _train_in_background


class TestTrainingState(unittest.TestCase):
    def test_initial_state(self):
        state = TrainingState()
        self.assertEqual(state.status, TrainingStatus.IDLE)
        self.assertEqual(state.progress_message, "")
        self.assertEqual(state.error_message, "")
        self.assertIsNone(state.model_params)
        self.assertIsNone(state.start_time)
        self.assertIsNone(state.end_time)

    def test_is_running_idle(self):
        state = TrainingState()
        self.assertFalse(state.is_running)

    def test_is_running_loading(self):
        state = TrainingState(status=TrainingStatus.LOADING_DATA)
        self.assertTrue(state.is_running)

    def test_is_running_training(self):
        state = TrainingState(status=TrainingStatus.TRAINING)
        self.assertTrue(state.is_running)

    def test_is_running_completed(self):
        state = TrainingState(status=TrainingStatus.COMPLETED)
        self.assertFalse(state.is_running)

    def test_is_running_failed(self):
        state = TrainingState(status=TrainingStatus.FAILED)
        self.assertFalse(state.is_running)

    def test_elapsed_seconds_not_started(self):
        state = TrainingState()
        self.assertEqual(state.elapsed_seconds, 0.0)

    def test_elapsed_seconds_running(self):
        state = TrainingState(start_time=time.time() - 5.0)
        elapsed = state.elapsed_seconds
        self.assertGreater(elapsed, 4.5)
        self.assertLess(elapsed, 6.0)

    def test_elapsed_seconds_completed(self):
        start = time.time() - 10.0
        end = start + 5.0
        state = TrainingState(start_time=start, end_time=end)
        self.assertAlmostEqual(state.elapsed_seconds, 5.0, places=1)


class TestTrainingStatusEnum(unittest.TestCase):
    def test_all_statuses(self):
        self.assertEqual(TrainingStatus.IDLE.value, "idle")
        self.assertEqual(TrainingStatus.LOADING_DATA.value, "loading_data")
        self.assertEqual(TrainingStatus.TRAINING.value, "training")
        self.assertEqual(TrainingStatus.COMPLETED.value, "completed")
        self.assertEqual(TrainingStatus.FAILED.value, "failed")


class TestBackgroundTraining(unittest.TestCase):
    @patch('ai.features.Features')
    @patch('ai.xgboost.XGBoostRegressorModel')
    @patch('ai.training_service.joblib')
    def test_successful_training(self, mock_joblib, mock_model_cls, mock_features_cls):
        """Test that background training updates state correctly on success."""
        import pandas as pd

        # Mock Features
        mock_feat_instance = MagicMock()
        mock_feat_instance.fetch_features_table.return_value = pd.DataFrame({
            'id': [1, 2], 'race_id': ['r1', 'r2'], 'event_id': [1, 2],
            'bib': ['b1', 'b2'], 'feature1': [1.0, 2.0], 'time': ['01:00:00', '02:00:00']
        })
        mock_features_cls.return_value = mock_feat_instance

        # Mock Model
        mock_model_instance = MagicMock()
        mock_model_instance.model.get_params.return_value = {'param1': 'value1'}
        mock_model_cls.return_value = mock_model_instance

        state = TrainingState()
        _train_in_background(
            state=state,
            metadata_features=[(1, 'r1', 'b1')],
            db_path='test.db',
            model_save_path='test_model.pkl',
        )

        self.assertEqual(state.status, TrainingStatus.COMPLETED)
        self.assertIsNotNone(state.model_params)
        self.assertIn("Training complete", state.progress_message)
        self.assertIsNotNone(state.end_time)

    def test_failed_training(self):
        """Test that background training updates state correctly on failure."""
        state = TrainingState()

        with patch('ai.features.Features', side_effect=Exception("DB error")):
            _train_in_background(
                state=state,
                metadata_features=[(1, 'r1', 'b1')],
                db_path='nonexistent.db',
                model_save_path='test_model.pkl',
            )

        self.assertEqual(state.status, TrainingStatus.FAILED)
        self.assertIn("DB error", state.error_message)
        self.assertIsNotNone(state.end_time)

    @patch('ai.features.Features')
    @patch('ai.xgboost.XGBoostRegressorModel')
    @patch('ai.training_service.joblib')
    def test_start_background_training_thread(self, mock_joblib, mock_model_cls, mock_features_cls):
        """Test that start_background_training returns a running thread."""
        import pandas as pd

        mock_feat_instance = MagicMock()
        mock_feat_instance.fetch_features_table.return_value = pd.DataFrame({
            'id': [1], 'race_id': ['r1'], 'event_id': [1],
            'bib': ['b1'], 'feature1': [1.0], 'time': ['01:00:00']
        })
        mock_features_cls.return_value = mock_feat_instance

        mock_model_instance = MagicMock()
        mock_model_instance.model.get_params.return_value = {}
        mock_model_cls.return_value = mock_model_instance

        state = TrainingState()
        thread = start_background_training(
            state=state,
            metadata_features=[(1, 'r1', 'b1')],
            db_path='test.db',
            model_save_path='test_model.pkl',
        )

        self.assertTrue(thread.is_alive() or state.status == TrainingStatus.COMPLETED)
        thread.join(timeout=10)
        self.assertEqual(state.status, TrainingStatus.COMPLETED)


if __name__ == '__main__':
    unittest.main()
