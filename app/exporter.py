"""Data export helpers for preview CSV and GAMS-friendly long data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype


PREVIEW_FILENAME = "exported_preview.csv"
LONG_FILENAME = "exported_data_long.csv"


class ExportError(RuntimeError):
    """Raised when data cannot be exported for downstream GAMS processing."""


def save_preview_csv(dataframe: pd.DataFrame, output_dir: Path) -> Path:
    """Save the preview data to CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / PREVIEW_FILENAME
    dataframe.to_csv(output_path, index=False)
    return output_path


def to_long_numeric_format(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert numeric columns to the obs-column_name-value long format."""
    numeric_columns = [
        column_name
        for column_name in dataframe.columns
        if is_numeric_dtype(dataframe[column_name])
    ]
    if not numeric_columns:
        raise ExportError(
            "The selected result contains no numeric columns. "
            "Choose at least one numeric column before running GAMS."
        )

    working_copy = dataframe.loc[:, numeric_columns].copy()
    working_copy.insert(0, "obs", range(1, len(working_copy) + 1))
    long_frame = working_copy.melt(
        id_vars="obs",
        value_vars=numeric_columns,
        var_name="column_name",
        value_name="value",
    )
    return long_frame.loc[:, ["obs", "column_name", "value"]]


def save_long_csv(dataframe: pd.DataFrame, output_dir: Path) -> Path:
    """Convert the provided data to long numeric format and save it."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / LONG_FILENAME
    long_frame = to_long_numeric_format(dataframe)
    long_frame.to_csv(output_path, index=False)
    return output_path
