"""Shared utilities for configuration, paths, and logging."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
GAMS_DIR = PROJECT_ROOT / "gams"

APP_LOGGER_NAME = "mysql_to_gams_importer"
RUNTIME_CONFIG_KEYS = {"gams_executable", "gams_studio_path"}


@dataclass(slots=True)
class RuntimeConfig:
    """Optional local runtime settings for GAMS integration."""

    gams_executable: Path | None = None
    gams_studio_path: Path | None = None


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

    placeholder_values = {
        "host": {"host", "your-mysql-host"},
        "database": {"your_database_name"},
        "user": {"your_database_user"},
        "password": {"your_password_here"},
    }
    invalid_fields = [
        field_name
        for field_name, placeholders in placeholder_values.items()
        if str(config.get(field_name, "")).strip() in placeholders
    ]
    if invalid_fields:
        raise ValueError(
            "Database configuration still contains placeholder values for: "
            + ", ".join(invalid_fields)
            + ". Update config/db_config.json before connecting."
        )

    return config, warnings


def _load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a JSON object: {path}")

    return data


def _resolve_optional_path(value: Any) -> Path | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None

    path = Path(normalized).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve(strict=False)


def load_runtime_config() -> tuple[RuntimeConfig, list[str]]:
    """Load optional local runtime settings for GAMS executable discovery."""
    local_config = CONFIG_DIR / "app_config.json"
    example_config = CONFIG_DIR / "app_config.example.json"

    selected_path = local_config if local_config.exists() else example_config
    if not selected_path.exists():
        return RuntimeConfig(), []

    config = _load_json_file(selected_path)
    warnings: list[str] = []

    unknown_keys = sorted(set(config).difference(RUNTIME_CONFIG_KEYS))
    if unknown_keys:
        warnings.append(
            "Ignoring unknown keys in runtime configuration: "
            + ", ".join(unknown_keys)
        )

    return (
        RuntimeConfig(
            gams_executable=_resolve_optional_path(config.get("gams_executable")),
            gams_studio_path=_resolve_optional_path(config.get("gams_studio_path")),
        ),
        warnings,
    )
