"""Unit tests for exporter transformations."""

from __future__ import annotations

import pandas as pd
import pytest

from app.exporter import ExportError, to_long_numeric_format


def test_to_long_numeric_format_preserves_numeric_columns_and_obs() -> None:
    dataframe = pd.DataFrame(
        {
            "farm_id": [101, 102],
            "year": [2023, 2024],
            "label": ["A", "B"],
            "score": [12.5, 15.0],
        }
    )

    result = to_long_numeric_format(dataframe)

    expected = pd.DataFrame(
        {
            "obs": [1, 2, 1, 2, 1, 2],
            "column_name": ["farm_id", "farm_id", "year", "year", "score", "score"],
            "value": [101.0, 102.0, 2023.0, 2024.0, 12.5, 15.0],
        }
    )

    pd.testing.assert_frame_equal(result.reset_index(drop=True), expected)


def test_to_long_numeric_format_raises_when_no_numeric_columns_exist() -> None:
    dataframe = pd.DataFrame({"name": ["x", "y"], "category": ["a", "b"]})

    with pytest.raises(ExportError):
        to_long_numeric_format(dataframe)
