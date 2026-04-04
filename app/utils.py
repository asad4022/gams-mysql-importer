"""Shared utilities for configuration and logging."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
GAMS_DIR = PROJECT_ROOT / "gams"

APP_LOGGER_NAME = "mysql_to_gams_importer"


def configure_logging(log_file: Path | None = None) -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger(APP_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def load_db_config() -> tuple[dict[str, Any], list[str]]:
    """Load database configuration from the local or example config file."""
    local_config = CONFIG_DIR / "db_config.json"
    example_config = CONFIG_DIR / "db_config.example.json"

    warnings: list[str] = []
    selected_path = local_config if local_config.exists() else example_config

    if not local_config.exists():
        warnings.append(
            "config/db_config.json not found; using config/db_config.example.json."
        )

    if not selected_path.exists():
        raise FileNotFoundError(
            "No database configuration file found. Expected config/db_config.json "
            "or config/db_config.example.json."
        )

    with selected_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    required_keys = {"host", "port", "database", "user", "password"}
    missing = sorted(required_keys.difference(config))
    if missing:
        raise KeyError(
            f"Database configuration is missing required keys: {', '.join(missing)}"
        )

    return config, warnings
