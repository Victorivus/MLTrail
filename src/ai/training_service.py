"""Background model training service using threading."""
import threading
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import joblib
import pandas as pd

logger = logging.getLogger(__name__)


class TrainingStatus(Enum):
    IDLE = "idle"
    LOADING_DATA = "loading_data"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrainingState:
    """Shared state between background thread and Streamlit UI."""
    status: TrainingStatus = TrainingStatus.IDLE
    progress_message: str = ""
    error_message: str = ""
    model_params: Optional[dict] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_running(self) -> bool:
        return self.status in (TrainingStatus.LOADING_DATA, TrainingStatus.TRAINING)


def _train_in_background(
    state: TrainingState,
    metadata_features: list,
    db_path: str,
    model_save_path: str,
) -> None:
    """Run model training in a background thread. Updates `state` as it progresses."""
    try:
        state.start_time = time.time()

        # Phase 1: Load features
        state.status = TrainingStatus.LOADING_DATA
        state.progress_message = "Loading and preparing training data..."
        logger.info("Background training: loading features")

        from ai.features import Features
        from ai.xgboost import XGBoostRegressorModel

        feat = Features(metadata_features, db_path)
        data = feat.fetch_features_table().drop(columns=['id', 'race_id', 'event_id', 'bib'])

        # Phase 2: Train
        state.status = TrainingStatus.TRAINING
        state.progress_message = "Training ML model (GridSearchCV)... This may take several minutes."
        logger.info("Background training: starting GridSearchCV")

        rgs = XGBoostRegressorModel(df=data, target_column='time')
        rgs.train()

        # Phase 3: Save
        state.progress_message = "Saving model..."
        state.model_params = rgs.model.get_params()
        joblib.dump(rgs.model, model_save_path)

        state.status = TrainingStatus.COMPLETED
        state.end_time = time.time()
        state.progress_message = f"Training complete in {state.elapsed_seconds:.1f}s"
        logger.info("Background training: completed in %.1fs", state.elapsed_seconds)

    except Exception as e:
        state.status = TrainingStatus.FAILED
        state.end_time = time.time()
        state.error_message = str(e)
        state.progress_message = f"Training failed: {e}"
        logger.exception("Background training failed")


def start_background_training(
    state: TrainingState,
    metadata_features: list,
    db_path: str,
    model_save_path: str,
) -> threading.Thread:
    """Start training in a daemon thread. Returns the thread handle."""
    thread = threading.Thread(
        target=_train_in_background,
        args=(state, metadata_features, db_path, model_save_path),
        daemon=True,
        name="ml-training",
    )
    thread.start()
    logger.info("Background training thread started")
    return thread
