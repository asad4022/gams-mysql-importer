"""Unit tests for exporter transformations and generated GAMS artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.exporter import (
    ExportError,
    export_import_jobs,
    to_long_numeric_format,
    validate_gams_symbol_name,
)
from app.models import ImportJob, MaterializedImportJob


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


def test_validate_gams_symbol_name_rejects_reserved_name() -> None:
    with pytest.raises(ExportError):
        validate_gams_symbol_name("data")


def test_export_import_jobs_generates_runtime_and_consumer_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "data"
    gams_dir = tmp_path / "gams"

    jobs = [
        MaterializedImportJob(
            job=ImportJob(
                table_name="CERTIFICAZIONE",
                selected_columns=["profit", "capacity"],
                max_rows=5,
                symbol_name="certificationData",
            ),
            dataframe=pd.DataFrame({"profit": [10, 20], "capacity": [1, 2]}),
        ),
        MaterializedImportJob(
            job=ImportJob(
                table_name="COSTO_LAVORO",
                selected_columns=["cost"],
                max_rows=5,
                symbol_name="laborCostData",
                where_clause="Anno = 2023",
            ),
            dataframe=pd.DataFrame({"cost": [5, 6]}),
        ),
    ]

    artifacts = export_import_jobs(jobs, output_dir, gams_dir)

    runtime_text = artifacts.generated_runtime_include.read_text(encoding="utf-8")
    symbol_text = artifacts.generated_symbol_include.read_text(encoding="utf-8")
    example_text = artifacts.generated_example_model.read_text(encoding="utf-8")

    assert "newName: certificationData" in runtime_text
    assert "newName: laborCostData" in runtime_text
    assert "newName: data" in runtime_text
    assert "$load obs col data" in symbol_text
    assert "$load obs__certificationData col__certificationData certificationData" in symbol_text
    assert "display data, totalPrimaryData, certificationData, laborCostData" in example_text
    assert artifacts.primary_symbol_name == "certificationData"
