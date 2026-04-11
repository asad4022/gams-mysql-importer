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
                selected_columns=["sku", "profit", "capacity"],
                max_rows=5,
                symbol_name="certificationData",
                semantic_roles={"profit": "profit", "capacity": "capacity"},
                structured_index_columns=["sku"],
                structured_value_columns=["profit", "capacity"],
            ),
            dataframe=pd.DataFrame({"sku": ["A", "B"], "profit": [10, 20], "capacity": [1, 2]}),
        ),
        MaterializedImportJob(
            job=ImportJob(
                table_name="COSTO_LAVORO",
                selected_columns=["resource_id", "cost"],
                max_rows=5,
                symbol_name="laborCostData",
                where_clause="Anno = 2023",
                semantic_roles={"resource_id": "index", "cost": "cost"},
            ),
            dataframe=pd.DataFrame({"resource_id": [101, 102], "cost": [5, 6]}),
        ),
    ]

    artifacts = export_import_jobs(jobs, output_dir, gams_dir)

    runtime_text = artifacts.generated_runtime_include.read_text(encoding="utf-8")
    symbol_text = artifacts.generated_symbol_include.read_text(encoding="utf-8")
    example_text = artifacts.generated_example_model.read_text(encoding="utf-8")
    multi_job_example_text = artifacts.generated_multi_job_example_model.read_text(
        encoding="utf-8"
    )
    reconciliation_example_text = artifacts.generated_reconciliation_example_model.read_text(
        encoding="utf-8"
    )
    modeling_helper_text = artifacts.generated_modeling_helper_include.read_text(
        encoding="utf-8"
    )
    reconciliation_helper_text = artifacts.generated_reconciliation_helper_include.read_text(
        encoding="utf-8"
    )
    semantic_declarations_text = artifacts.generated_semantic_declarations_include.read_text(
        encoding="utf-8"
    )
    semantic_mapping_text = artifacts.generated_semantic_mapping_include.read_text(
        encoding="utf-8"
    )
    structured_declarations_text = artifacts.generated_structured_declarations_include.read_text(
        encoding="utf-8"
    )
    structured_assignments_text = artifacts.generated_structured_assignments_include.read_text(
        encoding="utf-8"
    )
    manifest_text = artifacts.manifest_csv.read_text(encoding="utf-8")
    symbol_catalog_text = artifacts.symbol_catalog_csv.read_text(encoding="utf-8")
    reconciliation_catalog_text = artifacts.reconciliation_catalog_csv.read_text(encoding="utf-8")
    semantic_coordination_text = artifacts.semantic_coordination_csv.read_text(encoding="utf-8")

    assert "name: certificationData" in runtime_text
    assert "name: laborCostData" in runtime_text
    assert "name: data" in runtime_text
    assert "$onMultiR" in symbol_text
    assert "$load obs__certificationData" in symbol_text
    assert "$load col__laborCostData" in symbol_text
    assert "$load data" in symbol_text
    assert "$load certificationData" in symbol_text
    assert "$load laborCostData" in symbol_text
    assert "$load profit__certificationData" in symbol_text
    assert "$load cost__laborCostData" in symbol_text
    assert "$load structuredIndex1__certificationData" in symbol_text
    assert "$load certificationData__profit" in symbol_text
    assert "$load certificationData__capacity" in symbol_text
    assert "$offMulti" in symbol_text
    assert "display data, totalPrimaryData, certificationData, laborCostData" in example_text
    assert '$include "gams/generated_modeling_helpers.gms"' in multi_job_example_text
    assert '$include "gams/generated_reconciliation_helpers.gms"' in multi_job_example_text
    assert "genericCoverage = card(genericImportedSymbol);" in multi_job_example_text
    assert "total__certificationData" in multi_job_example_text
    assert "total__laborCostData" in multi_job_example_text
    assert '$include "gams/generated_reconciliation_helpers.gms"' in reconciliation_example_text
    assert "reconciledPairCount = card(reconcilableJobPair);" in reconciliation_example_text
    assert "jobProvidesSemanticRole" in reconciliation_example_text
    assert "importJob(*) \"import jobs from the current basket\" / 'certificationData', 'laborCostData' /" in modeling_helper_text
    assert "genericImportedSymbol(importJob,*)" in modeling_helper_text
    assert "semanticDerivedSymbol(importJob,*)" in modeling_helper_text
    assert "structuredDerivedSymbol(importJob,*)" in modeling_helper_text
    assert "sharedDimensionLabel(importJob,*)" in modeling_helper_text
    assert "genericImportedSymbol('certificationData','data') = yes;" in modeling_helper_text
    assert "semanticDerivedSymbol('certificationData','profit__certificationData') = yes;" in modeling_helper_text
    assert "structuredDerivedSymbol('certificationData','certificationData__profit') = yes;" in modeling_helper_text
    assert "sharedDimensionLabel('certificationData','obs') = yes;" in modeling_helper_text
    assert "sharedDimensionLabel('certificationData','col') = yes;" in modeling_helper_text
    assert "structuredRank('certificationData') = 1;" in modeling_helper_text
    assert "semanticRoleCount('laborCostData') = 1;" in modeling_helper_text
    assert "coordinationRole(*) \"semantic roles tracked for reconciliation\"" in reconciliation_helper_text
    assert "reconcilableJobPair(importJob,importJob)" in reconciliation_helper_text
    assert "jobProvidesSemanticRole(importJob,coordinationRole)" in reconciliation_helper_text
    assert "recommendedCoordinationHint(importJob,importJob,*)" in reconciliation_helper_text
    assert "jobProvidesSemanticRole('certificationData','profit') = yes;" in reconciliation_helper_text
    assert "jobProvidesSemanticRole('laborCostData','cost') = yes;" in reconciliation_helper_text
    assert "Set requestedSemanticRole__certificationData(semanticRole)" in semantic_declarations_text
    assert "Parameter profit__certificationData(obs__certificationData)" in semantic_declarations_text
    assert "requestedSemanticRole__certificationData('profit') = yes;" in semantic_mapping_text
    assert "requestedSemanticRole__laborCostData('index') = yes;" in semantic_mapping_text
    assert "semanticMappingReady__laborCostData" in semantic_mapping_text
    assert "Set structuredIndex1__certificationData(*)" in structured_declarations_text
    assert "/ 'A', 'B' /;" in structured_declarations_text
    assert "Parameter certificationData__profit(structuredIndex1__certificationData)" in structured_declarations_text
    assert "certificationData__profit('A') = 10.0;" in structured_assignments_text
    assert "STRUCTURED_SYMBOL_READY: certificationData" in structured_assignments_text
    assert "STRUCTURED_SYMBOL_SKIPPED: laborCostData" in structured_assignments_text
    assert "profit:profit" in manifest_text
    assert "resource_id:index" in manifest_text
    assert "sku" in manifest_text
    assert "profit,capacity" in manifest_text
    assert "generic_symbol,generic_dimensions" in manifest_text
    assert "semantic_mapped_symbols" in manifest_text
    assert "structured_derived_symbols" in manifest_text
    assert "structured_dimensions" in manifest_text
    assert "provided_semantic_roles" in manifest_text
    assert "likely_shared_with" in manifest_text
    assert "reconciliation_notes" in manifest_text
    assert "certificationData,semantic,profit__certificationData,obs" in symbol_catalog_text
    assert (
        "certificationData,structured,certificationData__profit,structuredIndex1"
        in symbol_catalog_text
    )
    assert "laborCostData,semantic,cost__laborCostData,obs" in symbol_catalog_text
    assert "related_jobs" in symbol_catalog_text
    assert "left_symbol,right_symbol,compatibility_score" in reconciliation_catalog_text
    assert "complementary_semantic_roles" in reconciliation_catalog_text
    assert "semantic_role,provider_symbols,provider_parameters" in semantic_coordination_text
    assert "profit,certificationData,profit__certificationData(obs)" in semantic_coordination_text
    assert artifacts.primary_symbol_name == "certificationData"
