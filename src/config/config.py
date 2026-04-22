import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
from config.logging_config import setup_logging

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables."""
    package_dir_path: str = ""
    data_dir_path: str = ""
    db_filename: str = "events.db"
    model_filename: str = "model.pkl"
    plots_dir: str = "plots"
    log_level: str = "INFO"

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir_path, self.db_filename)

    @property
    def model_path(self) -> str:
        return os.path.join(self.data_dir_path, self.model_filename)

    @property
    def plots_dir_path(self) -> str:
        # An absolute PLOTS_DIR lets users redirect plots outside DATA_DIR_PATH;
        # a relative value keeps them co-located with the data.
        return os.path.join(self.data_dir_path, self.plots_dir)

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv(override=True)
        config = cls(
            package_dir_path=os.environ.get("PACKAGE_DIR_PATH", "."),
            data_dir_path=os.environ.get("DATA_DIR_PATH", "./data"),
            db_filename=os.environ.get("DB_FILENAME", "events.db"),
            model_filename=os.environ.get("MODEL_FILENAME", "model.pkl"),
            plots_dir=os.environ.get("PLOTS_DIR", "plots"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
        setup_logging(config.log_level)
        logger.info("Config loaded: PACKAGE_DIR_PATH=%s, DATA_DIR_PATH=%s",
                     config.package_dir_path, config.data_dir_path)
        return config


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get or create the singleton application config."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config
