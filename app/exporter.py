"""Data export helpers for preview CSV and reusable GAMS symbol handoff."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

from .models import ExportArtifacts, MaterializedImportJob, SEMANTIC_ROLES


PREVIEW_FILENAME = "exported_preview.csv"
LONG_FILENAME = "exported_data_long.csv"
IMPORT_JOB_DIRNAME = "import_jobs"
MANIFEST_FILENAME = "import_jobs_manifest.csv"
SYMBOL_CATALOG_FILENAME = "imported_symbol_catalog.csv"
GENERATED_RUNTIME_INCLUDE = "generated_import_runtime.gms"
GENERATED_SYMBOL_INCLUDE = "generated_import_symbols.gms"
GENERATED_MODELING_HELPER_INCLUDE = "generated_modeling_helpers.gms"
GENERATED_EXAMPLE_MODEL = "example_use_imported_symbols.gms"
GENERATED_MULTI_JOB_EXAMPLE_MODEL = "example_multi_job_integration.gms"
GENERATED_UNLOAD_INCLUDE = "generated_unload_symbols.gms"
GENERATED_SEMANTIC_DECLARATIONS_INCLUDE = "generated_semantic_declarations.gms"
GENERATED_SEMANTIC_MAPPING_INCLUDE = "generated_semantic_mapping.gms"
GENERATED_STRUCTURED_DECLARATIONS_INCLUDE = "generated_structured_declarations.gms"
GENERATED_STRUCTURED_ASSIGNMENTS_INCLUDE = "generated_structured_assignments.gms"

SYMBOL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_SYMBOL_NAMES = {
    "obs",
    "col",
    "data",
    "meanByColumn",
    "profit",
    "capacity",
    "cost",
    "demand",
    "mappingReady",
    "optimizationSolved",
    "semanticRole",
}


class ExportError(RuntimeError):
    """Raised when data cannot be exported for downstream GAMS processing."""


def validate_gams_symbol_name(symbol_name: str) -> str:
    """Validate a GAMS output symbol name for safe reuse."""
    normalized = symbol_name.strip()
    if not normalized:
        raise ExportError("Output symbol name is required for each import job.")
    if not SYMBOL_PATTERN.match(normalized):
        raise ExportError(
            "Output symbol name must start with a letter or underscore and contain "
            "only letters, digits, and underscores."
        )
    if normalized in RESERVED_SYMBOL_NAMES:
        raise ExportError(
            f"Output symbol name '{normalized}' is reserved. Choose a different symbol name."
        )
    return normalized


def validate_semantic_roles(selected_columns: list[str], semantic_roles: dict[str, str]) -> dict[str, str]:
    """Validate semantic role assignments for a queued import job."""
    selected_set = set(selected_columns)
    cleaned: dict[str, str] = {}
    for column_name, role in semantic_roles.items():
        if column_name not in selected_set:
            continue
        normalized_role = role.strip().lower()
        if normalized_role not in SEMANTIC_ROLES:
            raise ExportError(
                f"Unsupported semantic role '{role}' for column '{column_name}'."
            )
        cleaned[column_name] = normalized_role
    return cleaned


def validate_structured_columns(
    dataframe: pd.DataFrame,
    selected_columns: list[str],
    index_columns: list[str],
    value_columns: list[str],
) -> tuple[list[str], list[str]]:
    """Validate optional structured symbol metadata for a queued import job."""
    selected_set = set(selected_columns)
    cleaned_indexes = [column for column in index_columns if column in selected_set]
    cleaned_values = [column for column in value_columns if column in selected_set]

    if not cleaned_indexes and not cleaned_values:
        return [], []
    if not cleaned_indexes or not cleaned_values:
        raise ExportError(
            "Structured symbol generation requires at least one index column and at least one value column."
        )
    if len(cleaned_indexes) > 2:
        raise ExportError(
            "Structured symbol generation currently supports at most two index columns per import job."
        )

    overlap = sorted(set(cleaned_indexes).intersection(cleaned_values))
    if overlap:
        raise ExportError(
            "Structured index and value columns must be distinct. "
            f"Overlap detected: {', '.join(overlap)}."
        )

    nonnumeric_values = [
        column_name
        for column_name in cleaned_values
        if column_name not in dataframe.columns or not is_numeric_dtype(dataframe[column_name])
    ]
    if nonnumeric_values:
        raise ExportError(
            "Structured value columns must be numeric in the fetched result. "
            f"Non-numeric value columns: {', '.join(nonnumeric_values)}."
        )

    return cleaned_indexes, cleaned_values


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


def export_import_jobs(
    jobs: list[MaterializedImportJob],
    output_dir: Path,
    gams_dir: Path,
) -> ExportArtifacts:
    """Export multiple queued jobs into reusable GAMS-ready artifacts."""
    if not jobs:
        raise ExportError("No import jobs are available for export.")

    output_dir.mkdir(parents=True, exist_ok=True)
    gams_dir.mkdir(parents=True, exist_ok=True)
    job_directory = output_dir / IMPORT_JOB_DIRNAME
    job_directory.mkdir(parents=True, exist_ok=True)

    validated_symbols: list[str] = []
    symbol_seen: set[str] = set()

    for materialized_job in jobs:
        symbol_name = validate_gams_symbol_name(materialized_job.job.symbol_name)
        if symbol_name in symbol_seen:
            raise ExportError(
                f"Output symbol name '{symbol_name}' is duplicated in the import basket."
            )
        symbol_seen.add(symbol_name)
        validated_symbols.append(symbol_name)
        validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )

    preview_csv = save_preview_csv(jobs[0].dataframe, output_dir)
    legacy_long_csv = save_long_csv(jobs[0].dataframe, output_dir)
    manifest_csv = _write_manifest(jobs, output_dir / MANIFEST_FILENAME)
    symbol_catalog_csv = _write_symbol_catalog(jobs, output_dir / SYMBOL_CATALOG_FILENAME)
    _write_job_csvs(jobs, validated_symbols, job_directory)

    generated_runtime_include = gams_dir / GENERATED_RUNTIME_INCLUDE
    generated_symbol_include = gams_dir / GENERATED_SYMBOL_INCLUDE
    generated_modeling_helper_include = gams_dir / GENERATED_MODELING_HELPER_INCLUDE
    generated_example_model = gams_dir / GENERATED_EXAMPLE_MODEL
    generated_multi_job_example_model = gams_dir / GENERATED_MULTI_JOB_EXAMPLE_MODEL
    generated_unload_include = gams_dir / GENERATED_UNLOAD_INCLUDE
    generated_semantic_declarations_include = gams_dir / GENERATED_SEMANTIC_DECLARATIONS_INCLUDE
    generated_semantic_mapping_include = gams_dir / GENERATED_SEMANTIC_MAPPING_INCLUDE
    generated_structured_declarations_include = gams_dir / GENERATED_STRUCTURED_DECLARATIONS_INCLUDE
    generated_structured_assignments_include = gams_dir / GENERATED_STRUCTURED_ASSIGNMENTS_INCLUDE

    _write_runtime_include(jobs, validated_symbols, generated_runtime_include)
    _write_semantic_mapping_includes(
        jobs,
        validated_symbols,
        generated_semantic_declarations_include,
        generated_semantic_mapping_include,
    )
    _write_structured_symbol_includes(
        jobs,
        validated_symbols,
        generated_structured_declarations_include,
        generated_structured_assignments_include,
    )
    _write_unload_include(jobs, validated_symbols, generated_unload_include)
    _write_symbol_include(jobs, validated_symbols, generated_symbol_include)
    _write_modeling_helper_include(jobs, validated_symbols, generated_modeling_helper_include)
    _write_example_consumer(jobs, validated_symbols, generated_example_model)
    _write_multi_job_example_consumer(
        jobs,
        validated_symbols,
        generated_multi_job_example_model,
    )

    return ExportArtifacts(
        preview_csv=preview_csv,
        legacy_long_csv=legacy_long_csv,
        job_directory=job_directory,
        manifest_csv=manifest_csv,
        symbol_catalog_csv=symbol_catalog_csv,
        generated_runtime_include=generated_runtime_include,
        generated_symbol_include=generated_symbol_include,
        generated_modeling_helper_include=generated_modeling_helper_include,
        generated_example_model=generated_example_model,
        generated_multi_job_example_model=generated_multi_job_example_model,
        generated_unload_include=generated_unload_include,
        generated_semantic_declarations_include=generated_semantic_declarations_include,
        generated_semantic_mapping_include=generated_semantic_mapping_include,
        generated_structured_declarations_include=generated_structured_declarations_include,
        generated_structured_assignments_include=generated_structured_assignments_include,
        symbol_names=validated_symbols,
        primary_symbol_name=validated_symbols[0],
    )


def _write_manifest(jobs: list[MaterializedImportJob], output_path: Path) -> Path:
    """Write a CSV manifest describing the queued import jobs."""
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "symbol_name",
                "table_name",
                "selected_columns",
                "max_rows",
                "where_clause",
                "primary_alias",
                "generic_symbol",
                "generic_dimensions",
                "semantic_roles",
                "semantic_mapped_symbols",
                "structured_index_columns",
                "structured_value_columns",
                "structured_derived_symbols",
                "structured_dimensions",
            ]
        )
        for index, materialized_job in enumerate(jobs):
            semantic_roles = validate_semantic_roles(
                materialized_job.job.selected_columns,
                materialized_job.job.semantic_roles,
            )
            structured_indexes, structured_values = validate_structured_columns(
                materialized_job.dataframe,
                materialized_job.job.selected_columns,
                materialized_job.job.structured_index_columns,
                materialized_job.job.structured_value_columns,
            )
            writer.writerow(
                [
                    materialized_job.job.symbol_name,
                    materialized_job.job.table_name,
                    ",".join(materialized_job.job.selected_columns),
                    materialized_job.job.max_rows,
                    materialized_job.job.where_clause,
                    "data(obs,col)" if index == 0 else "",
                    f"{materialized_job.job.symbol_name}(obs,col)",
                    "obs,col",
                    ";".join(f"{column}:{role}" for column, role in sorted(semantic_roles.items())),
                    ",".join(
                        f"{role}__{materialized_job.job.symbol_name}(obs)"
                        for role in sorted(set(semantic_roles.values()))
                        if role != "index"
                    ),
                    ",".join(structured_indexes),
                    ",".join(structured_values),
                    ",".join(
                        f"{_structured_parameter_name(materialized_job.job.symbol_name, value_column)}"
                        for value_column in structured_values
                    ),
                    " | ".join(
                        f"{_structured_parameter_name(materialized_job.job.symbol_name, value_column)}"
                        f"({','.join(f'i{position}' for position in range(1, len(structured_indexes) + 1))})"
                        for value_column in structured_values
                    ),
                ]
            )
    return output_path


def _write_symbol_catalog(jobs: list[MaterializedImportJob], output_path: Path) -> Path:
    """Write a row-per-symbol catalog for downstream multi-job modeling."""
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "job_symbol",
                "category",
                "symbol_name",
                "dimensions",
                "source_table",
                "source_columns",
                "details",
            ]
        )

        for index, materialized_job in enumerate(jobs):
            job = materialized_job.job
            semantic_roles = validate_semantic_roles(job.selected_columns, job.semantic_roles)
            structured_indexes, structured_values = validate_structured_columns(
                materialized_job.dataframe,
                job.selected_columns,
                job.structured_index_columns,
                job.structured_value_columns,
            )
            selected_columns = ",".join(job.selected_columns)

            writer.writerow(
                [
                    job.symbol_name,
                    "generic-primary" if index == 0 else "generic",
                    "data" if index == 0 else job.symbol_name,
                    "obs,col",
                    job.table_name,
                    selected_columns,
                    "Backward-compatible primary alias for the first job."
                    if index == 0
                    else "Reusable generic imported symbol.",
                ]
            )
            if index == 0:
                writer.writerow(
                    [
                        job.symbol_name,
                        "generic",
                        job.symbol_name,
                        "obs,col",
                        job.table_name,
                        selected_columns,
                        "Named generic imported symbol for the first job.",
                    ]
                )

            for role in sorted(set(semantic_roles.values())):
                if role == "index":
                    continue
                writer.writerow(
                    [
                        job.symbol_name,
                        "semantic",
                        f"{role}__{job.symbol_name}",
                        "obs",
                        job.table_name,
                        selected_columns,
                        f"Derived from semantic role '{role}'.",
                    ]
                )

            structured_dimensions = ",".join(
                f"structuredIndex{position}"
                for position in range(1, len(structured_indexes) + 1)
            )
            for value_column in structured_values:
                writer.writerow(
                    [
                        job.symbol_name,
                        "structured",
                        _structured_parameter_name(job.symbol_name, value_column),
                        structured_dimensions,
                        job.table_name,
                        selected_columns,
                        "Structured derived symbol from explicit index/value columns.",
                    ]
                )

    return output_path


def _write_job_csvs(
    jobs: list[MaterializedImportJob], validated_symbols: list[str], job_directory: Path
) -> None:
    """Write one long-format CSV per queued import job."""
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        job_csv = job_directory / f"{symbol_name}.csv"
        long_frame = to_long_numeric_format(materialized_job.dataframe)
        long_frame.to_csv(job_csv, index=False)


def _safe_gams_description(text: str) -> str:
    """Escape double quotes for generated GAMS explanatory text."""
    return text.replace('"', "'")


def _safe_gams_label(value: object) -> str:
    """Escape a runtime value for use as a quoted GAMS label."""
    return str(value).replace("'", "''")


def _obs_set_name(symbol_name: str) -> str:
    return f"obs__{symbol_name}"


def _col_set_name(symbol_name: str) -> str:
    return f"col__{symbol_name}"


def _structured_index_set_name(symbol_name: str, position: int) -> str:
    return f"structuredIndex{position}__{symbol_name}"


def _structured_parameter_name(symbol_name: str, value_column: str) -> str:
    normalized_value = re.sub(r"[^A-Za-z0-9_]", "_", value_column.strip()) or "value"
    if normalized_value[0].isdigit():
        normalized_value = f"value_{normalized_value}"
    return validate_gams_symbol_name(f"{symbol_name}__{normalized_value}")


def _write_runtime_include(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    output_path: Path,
) -> None:
    """Generate the runtime GAMS include that imports all queued symbols."""
    lines: list[str] = [
        "* Auto-generated by the Python importer. Do not edit manually.",
        "* This file declares the imported symbols and reconstructs them from CSV files.",
        "",
        "Sets",
        '    obs "primary observation set from the first import job"',
        '    col "primary column set from the first import job"',
    ]

    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        table_name = _safe_gams_description(materialized_job.job.table_name)
        lines.append(
            f'    {_obs_set_name(symbol_name)} "observation set for {symbol_name} from {table_name}"'
        )
        lines.append(
            f'    {_col_set_name(symbol_name)} "column set for {symbol_name} from {table_name}"'
        )
    lines[-1] = lines[-1] + ";"

    lines.extend(["", "Parameter", '    data(obs<, col<) "backward-compatible primary imported symbol"'])
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        description = _safe_gams_description(
            f"imported numeric data from {materialized_job.job.table_name}"
        )
        lines.append(
            f'    {symbol_name}({_obs_set_name(symbol_name)}<, {_col_set_name(symbol_name)}<) "{description}"'
        )
    lines[-1] = lines[-1] + ";"

    lines.extend(["", "$onEmbeddedCode Connect:"])
    for index, symbol_name in enumerate(validated_symbols):
        csv_path = f"data/{IMPORT_JOB_DIRNAME}/{symbol_name}.csv"
        lines.extend(
            [
                "- CSVReader:",
                f"    file: {csv_path}",
                f"    name: {symbol_name}",
                "    trace: 0",
                "    indexColumns: [1, 2]",
                "    valueColumns: [3]",
                "- GAMSWriter:",
                "    symbols:",
                f"      - name: {symbol_name}",
            ]
        )
        if index == 0:
            lines.extend(
                [
                    "- CSVReader:",
                    f"    file: {csv_path}",
                    "    name: data",
                    "    trace: 0",
                    "    indexColumns: [1, 2]",
                    "    valueColumns: [3]",
                    "- GAMSWriter:",
                    "    symbols:",
                    "      - name: data",
                ]
            )
    lines.extend(["$offEmbeddedCode", ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")

def _write_symbol_include(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    output_path: Path,
) -> None:
    """Generate a consumer-friendly include for loading imported symbols from GDX."""
    lines: list[str] = [
        "* Auto-generated helper include for loading imported SQL symbols into your own GAMS model.",
        "* Include this file after the import pipeline has created data/imported_data.gdx.",
        '* For multi-job downstream models, include "gams/generated_modeling_helpers.gms" as well.',
        "",
        "Sets",
        '    obs(*) "primary observation set from the first import job"',
        '    col(*) "primary column set from the first import job"',
    ]
    for symbol_name in validated_symbols:
        lines.append(f'    {_obs_set_name(symbol_name)}(*) "observation set for {symbol_name}"')
        lines.append(f'    {_col_set_name(symbol_name)}(*) "column set for {symbol_name}"')
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        index_columns, _value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )
        for position in range(1, len(index_columns) + 1):
            lines.append(
                f'    {_structured_index_set_name(symbol_name, position)}(*) '
                f'"structured index set {position} for {symbol_name}"'
            )
    lines[-1] = lines[-1] + ";"

    lines.extend(["", "Parameters", '    data(obs<, col<) "backward-compatible primary imported symbol"'])
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        description = _safe_gams_description(
            f"imported numeric data from {materialized_job.job.table_name}"
        )
        lines.append(
            f'    {symbol_name}({_obs_set_name(symbol_name)}<, {_col_set_name(symbol_name)}<) "{description}"'
        )
        for role in SEMANTIC_ROLES:
            if role == "index":
                continue
            lines.append(
                f'    {role}__{symbol_name}({_obs_set_name(symbol_name)}<) "{role} mapping for {symbol_name}"'
            )
        index_columns, value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )
        for value_column in value_columns:
            structured_name = _structured_parameter_name(symbol_name, value_column)
            domains = ", ".join(
                f"{_structured_index_set_name(symbol_name, position)}"
                for position in range(1, len(index_columns) + 1)
            )
            lines.append(
                f'    {structured_name}({domains}) "structured parameter for {symbol_name} from {value_column}"'
            )
    lines[-1] = lines[-1] + ";"

    lines.extend(
        [
            "",
            "* Load shared and per-job domain sets first so downstream parameters have stable domains.",
            "$gdxin data/imported_data.gdx",
            "$onMultiR",
            "$load obs",
            "$load col",
        ]
    )
    for symbol_name in validated_symbols:
        lines.append(f"$load {_obs_set_name(symbol_name)}")
        lines.append(f"$load {_col_set_name(symbol_name)}")
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        index_columns, _value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )
        for position in range(1, len(index_columns) + 1):
            lines.append(f"$load {_structured_index_set_name(symbol_name, position)}")

    lines.extend(["", "* Generic symbols", "$load data"])
    for symbol_name in validated_symbols:
        lines.append(f"$load {symbol_name}")
    lines.append("")
    lines.append("* Semantic mapped symbols")
    lines.append("")
    for symbol_name in validated_symbols:
        for role in SEMANTIC_ROLES:
            if role == "index":
                continue
            lines.append(f"$load {role}__{symbol_name}")
    lines.append("")
    lines.append("* Structured derived parameters")
    lines.append("")
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        _index_columns, value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )
        for value_column in value_columns:
            lines.append(f"$load {_structured_parameter_name(symbol_name, value_column)}")
    lines.extend(["$offMulti", "$gdxin", ""])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_example_consumer(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    output_path: Path,
) -> None:
    """Generate a small example showing how to consume current imported symbols."""
    lines: list[str] = [
        "$title Example Use Of Imported Symbols",
        "",
        "* Auto-generated example consumer for the current import basket.",
        '* It loads the current symbols from "data/imported_data.gdx" using the',
        '* generated include file and then performs a few simple calculations.',
        "",
        '$include "gams/generated_import_symbols.gms"',
        "",
        'Scalar totalPrimaryData "sum of all values in the primary imported symbol";',
        "totalPrimaryData = sum((obs, col), data(obs, col));",
        "",
    ]

    for symbol_name in validated_symbols[:2]:
        total_name = f"total__{symbol_name}"
        lines.extend(
            [
                f'Scalar {total_name} "sum of all values in {symbol_name}";',
                f"{total_name} = sum(({_obs_set_name(symbol_name)}, {_col_set_name(symbol_name)}), "
                f"{symbol_name}({_obs_set_name(symbol_name)}, {_col_set_name(symbol_name)}));",
                "",
            ]
        )
        lines.extend(
            [
                f'Scalar totalProfit__{symbol_name} "sum of mapped profit values for {symbol_name}";',
                f"totalProfit__{symbol_name} = sum(({_obs_set_name(symbol_name)}), profit__{symbol_name}({_obs_set_name(symbol_name)}));",
                "",
            ]
        )

    display_items = ["data", "totalPrimaryData", *validated_symbols[:2]]
    display_items.extend(f"total__{symbol_name}" for symbol_name in validated_symbols[:2])
    display_items.extend(
        f"profit__{symbol_name}" for symbol_name in validated_symbols[:2]
    )
    for materialized_job, symbol_name in zip(jobs[:2], validated_symbols[:2], strict=True):
        _index_columns, value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )
        if value_columns:
            display_items.append(_structured_parameter_name(symbol_name, value_columns[0]))
    lines.append("display " + ", ".join(display_items) + ";")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_modeling_helper_include(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    output_path: Path,
) -> None:
    """Generate a helper include that documents and maps the current basket for multi-job models."""
    import_job_members = ", ".join(f"'{symbol_name}'" for symbol_name in validated_symbols) or "'none'"
    lines: list[str] = [
        "* Auto-generated helper include for combining multiple imported jobs in one GAMS model.",
        "* It declares a compact catalog of generic, semantic, and structured outputs for the current run.",
        "",
        "Sets",
        f'    importJob(*) "import jobs from the current basket" / {import_job_members} /',
        '    genericImportedSymbol(importJob,*) "generic imported symbols by job"',
        '    semanticDerivedSymbol(importJob,*) "semantic derived symbols by job"',
        '    structuredIndexSet(importJob,*) "structured index set identifiers by job"',
        '    structuredDerivedSymbol(importJob,*) "structured derived symbols by job"',
        '    sharedDimensionLabel(importJob,*) "dimension labels that help combine jobs downstream"',
        ";",
        "",
        "Parameter",
        '    structuredRank(importJob) "number of explicit structured index dimensions for each job"',
        '    semanticRoleCount(importJob) "number of non-index semantic role mappings for each job"',
        '    structuredValueCount(importJob) "number of structured derived value symbols for each job"',
        ";",
        "",
    ]

    for index, (materialized_job, symbol_name) in enumerate(zip(jobs, validated_symbols, strict=True)):
        job = materialized_job.job
        semantic_roles = validate_semantic_roles(job.selected_columns, job.semantic_roles)
        structured_indexes, structured_values = validate_structured_columns(
            materialized_job.dataframe,
            job.selected_columns,
            job.structured_index_columns,
            job.structured_value_columns,
        )
        lines.append(f"genericImportedSymbol('{symbol_name}','{symbol_name}') = yes;")
        if index == 0:
            lines.append(f"genericImportedSymbol('{symbol_name}','data') = yes;")
            lines.append(f"sharedDimensionLabel('{symbol_name}','data') = yes;")
        lines.append(f"sharedDimensionLabel('{symbol_name}','obs') = yes;")
        lines.append(f"sharedDimensionLabel('{symbol_name}','col') = yes;")

        semantic_count = 0
        for role in sorted(set(semantic_roles.values())):
            if role == "index":
                continue
            semantic_count += 1
            lines.append(
                f"semanticDerivedSymbol('{symbol_name}','{role}__{symbol_name}') = yes;"
            )
            lines.append(
                f"sharedDimensionLabel('{symbol_name}','obs') = yes;"
            )

        for position in range(1, len(structured_indexes) + 1):
            set_name = _structured_index_set_name(symbol_name, position)
            lines.append(f"structuredIndexSet('{symbol_name}','{set_name}') = yes;")
            lines.append(
                f"sharedDimensionLabel('{symbol_name}','{set_name}') = yes;"
            )

        for value_column in structured_values:
            structured_name = _structured_parameter_name(symbol_name, value_column)
            domain_signature = ",".join(
                _structured_index_set_name(symbol_name, position)
                for position in range(1, len(structured_indexes) + 1)
            )
            lines.append(
                f"structuredDerivedSymbol('{symbol_name}','{structured_name}') = yes;"
            )
            for position in range(1, len(structured_indexes) + 1):
                lines.append(
                    f"sharedDimensionLabel('{symbol_name}','{_structured_index_set_name(symbol_name, position)}') = yes;"
                )

        lines.append(f"structuredRank('{symbol_name}') = {len(structured_indexes)};")
        lines.append(f"semanticRoleCount('{symbol_name}') = {semantic_count};")
        lines.append(f"structuredValueCount('{symbol_name}') = {len(structured_values)};")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_multi_job_example_consumer(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    output_path: Path,
) -> None:
    """Generate an example downstream model that uses two imported jobs together."""
    lines: list[str] = [
        "$title Example Multi-Job Integration",
        "",
        "* Auto-generated example showing how to combine multiple imported jobs in one downstream model.",
        '$include "gams/generated_import_symbols.gms"',
        '$include "gams/generated_modeling_helpers.gms"',
        "",
        'Scalar genericCoverage "number of generic symbol mappings in the current helper catalog";',
        "genericCoverage = card(genericImportedSymbol);",
        "",
    ]

    if len(validated_symbols) >= 2:
        first_job = jobs[0]
        second_job = jobs[1]
        first_symbol = validated_symbols[0]
        second_symbol = validated_symbols[1]

        lines.extend(
            [
                f'Scalar total__{first_symbol} "generic total for {first_symbol}";',
                f"total__{first_symbol} = sum(({_obs_set_name(first_symbol)}, {_col_set_name(first_symbol)}), "
                f"{first_symbol}({_obs_set_name(first_symbol)}, {_col_set_name(first_symbol)}));",
                f'Scalar total__{second_symbol} "generic total for {second_symbol}";',
                f"total__{second_symbol} = sum(({_obs_set_name(second_symbol)}, {_col_set_name(second_symbol)}), "
                f"{second_symbol}({_obs_set_name(second_symbol)}, {_col_set_name(second_symbol)}));",
                "",
            ]
        )

        first_indexes, first_values = validate_structured_columns(
            first_job.dataframe,
            first_job.job.selected_columns,
            first_job.job.structured_index_columns,
            first_job.job.structured_value_columns,
        )
        second_indexes, second_values = validate_structured_columns(
            second_job.dataframe,
            second_job.job.selected_columns,
            second_job.job.structured_index_columns,
            second_job.job.structured_value_columns,
        )
        if first_values:
            first_structured = _structured_parameter_name(first_symbol, first_values[0])
            first_domain = ", ".join(
                _structured_index_set_name(first_symbol, position)
                for position in range(1, len(first_indexes) + 1)
            )
            lines.extend(
                [
                    f'Scalar totalStructured__{first_symbol} "structured total for {first_symbol}";',
                    f"totalStructured__{first_symbol} = sum(({first_domain}), {first_structured}({first_domain}));",
                    "",
                ]
            )
        if second_values:
            second_structured = _structured_parameter_name(second_symbol, second_values[0])
            second_domain = ", ".join(
                _structured_index_set_name(second_symbol, position)
                for position in range(1, len(second_indexes) + 1)
            )
            lines.extend(
                [
                    f'Scalar totalStructured__{second_symbol} "structured total for {second_symbol}";',
                    f"totalStructured__{second_symbol} = sum(({second_domain}), {second_structured}({second_domain}));",
                    "",
                ]
            )

        display_items = [
            "importJob",
            "genericImportedSymbol",
            "semanticDerivedSymbol",
            "structuredIndexSet",
            "structuredDerivedSymbol",
            "sharedDimensionLabel",
            "structuredRank",
            "semanticRoleCount",
            "structuredValueCount",
            "genericCoverage",
            f"total__{first_symbol}",
            f"total__{second_symbol}",
        ]
        if first_values:
            display_items.append(f"totalStructured__{first_symbol}")
        if second_values:
            display_items.append(f"totalStructured__{second_symbol}")
        lines.append("display " + ", ".join(display_items) + ";")
    else:
        lines.extend(
            [
                "* At least two queued jobs are recommended for this example.",
                "display importJob, genericImportedSymbol, semanticDerivedSymbol, structuredDerivedSymbol;",
            ]
        )

    lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _role_assignment_set_name(symbol_name: str) -> str:
    return f"requestedSemanticColumn__{symbol_name}"


def _role_request_set_name(symbol_name: str) -> str:
    return f"requestedSemanticRole__{symbol_name}"


def _role_materialized_set_name(symbol_name: str) -> str:
    return f"semanticColumn__{symbol_name}"


def _role_match_count_name(symbol_name: str) -> str:
    return f"semanticRoleMatchCount__{symbol_name}"


def _role_value_name(symbol_name: str) -> str:
    return f"semanticValue__{symbol_name}"


def _role_scalar_name(prefix: str, symbol_name: str) -> str:
    return f"{prefix}__{symbol_name}"


def _write_semantic_mapping_includes(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    declaration_output_path: Path,
    runtime_output_path: Path,
) -> None:
    """Generate symbol-specific semantic role declarations and assignments."""
    declaration_lines: list[str] = [
        "* Auto-generated semantic role declarations for the current import basket.",
        "",
    ]
    runtime_lines: list[str] = [
        "* Auto-generated semantic role mapping for the current import basket.",
        "* Semantic roles are advisory metadata from the GUI. Generic symbol imports remain available even when mappings are incomplete.",
        "",
    ]

    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        roles = validate_semantic_roles(
            materialized_job.job.selected_columns,
            materialized_job.job.semantic_roles,
        )
        table_name = _safe_gams_description(materialized_job.job.table_name)
        declaration_lines.extend(
            [
                f"* Semantic mapping for {symbol_name} from {table_name}",
                f"Set {_role_assignment_set_name(symbol_name)}(semanticRole, *) "
                f'"requested semantic role assignments from the GUI for {symbol_name}";',
                f"Set {_role_request_set_name(symbol_name)}(semanticRole) "
                f'"semantic roles requested for {symbol_name}";',
                f"Set {_role_materialized_set_name(symbol_name)}(semanticRole, {_col_set_name(symbol_name)}) "
                f'"materialized semantic role assignments for {symbol_name}";',
                f"Parameter {_role_match_count_name(symbol_name)}(semanticRole) "
                f'"number of materialized columns assigned to each semantic role for {symbol_name}";',
                f"Parameter {_role_value_name(symbol_name)}({_obs_set_name(symbol_name)}, semanticRole) "
                f'"role-oriented view of imported values for {symbol_name}";',
            ]
        )
        for role in SEMANTIC_ROLES:
            if role == "index":
                continue
            declaration_lines.append(
                f"Parameter {role}__{symbol_name}({_obs_set_name(symbol_name)}) "
                f'"mapped {role} parameter for {symbol_name}";'
            )
        declaration_lines.extend(
            [
                f"Scalar {_role_scalar_name('semanticMappingReady', symbol_name)} "
                f'"1 if non-index semantic roles for {symbol_name} were materialized without ambiguity";',
                f"Scalar {_role_scalar_name('semanticMissingCount', symbol_name)} "
                f'"number of requested roles for {symbol_name} that were not materialized";',
                f"Scalar {_role_scalar_name('semanticAmbiguousCount', symbol_name)} "
                f'"number of requested roles for {symbol_name} that matched multiple columns";',
                "",
            ]
        )

        for column_name, role in sorted(roles.items()):
            runtime_lines.append(
                f"{_role_assignment_set_name(symbol_name)}('{role}','{column_name}') = yes;"
            )
        for role in sorted(set(roles.values())):
            runtime_lines.append(f"{_role_request_set_name(symbol_name)}('{role}') = yes;")
        if not roles:
            runtime_lines.extend(
                [
                    f"* No semantic roles were requested for {symbol_name}.",
                    f"{_role_scalar_name('semanticMissingCount', symbol_name)} = 0;",
                    f"{_role_scalar_name('semanticAmbiguousCount', symbol_name)} = 0;",
                    f"{_role_scalar_name('semanticMappingReady', symbol_name)} = 1;",
                    f"{_role_match_count_name(symbol_name)}(semanticRole) = 0;",
                    f"{_role_value_name(symbol_name)}({_obs_set_name(symbol_name)}, semanticRole) = 0;",
                    f"put_utility 'log' / 'SEMANTIC_ROLE_STATUS: {symbol_name} requested roles -> none';",
                    "",
                ]
            )
        else:
            runtime_lines.extend(
                [
                    f"{_role_materialized_set_name(symbol_name)}(semanticRole, {_col_set_name(symbol_name)}) = "
                    f"{_role_assignment_set_name(symbol_name)}(semanticRole, {_col_set_name(symbol_name)});",
                    f"{_role_match_count_name(symbol_name)}(semanticRole) = sum("
                    f"{_role_materialized_set_name(symbol_name)}(semanticRole, {_col_set_name(symbol_name)}), 1);",
                    f"{_role_scalar_name('semanticMissingCount', symbol_name)} = sum("
                    f"semanticRole$({_role_request_set_name(symbol_name)}(semanticRole) and not sameas(semanticRole, 'index') and "
                    f"{_role_match_count_name(symbol_name)}(semanticRole) = 0), "
                    "1);",
                    f"{_role_scalar_name('semanticAmbiguousCount', symbol_name)} = sum("
                    f"semanticRole$({_role_request_set_name(symbol_name)}(semanticRole) and not sameas(semanticRole, 'index') and "
                    f"{_role_match_count_name(symbol_name)}(semanticRole) > 1), "
                    "1);",
                    f"{_role_scalar_name('semanticMappingReady', symbol_name)} = "
                    f"({_role_scalar_name('semanticMissingCount', symbol_name)} = 0 and "
                    f"{_role_scalar_name('semanticAmbiguousCount', symbol_name)} = 0);",
                    f"{_role_value_name(symbol_name)}({_obs_set_name(symbol_name)}, semanticRole) = sum("
                    f"{_role_materialized_set_name(symbol_name)}(semanticRole, {_col_set_name(symbol_name)}), "
                    f"{symbol_name}({_obs_set_name(symbol_name)}, {_col_set_name(symbol_name)}));",
                ]
            )
            for role in SEMANTIC_ROLES:
                if role == "index":
                    continue
                runtime_lines.append(
                    f"{role}__{symbol_name}({_obs_set_name(symbol_name)}) = "
                    f"{_role_value_name(symbol_name)}({_obs_set_name(symbol_name)}, '{role}');"
                )
            runtime_lines.extend(
                [
                    f"put_utility 'log' / 'SEMANTIC_ROLE_STATUS: {symbol_name} requested roles -> {', '.join(f'{column}:{role}' for column, role in sorted(roles.items()))}';",
                    f"put_utility 'log' / 'SEMANTIC_ROLE_RESULT: {symbol_name}';",
                    f"put_utility 'log' / '  missing=' {_role_scalar_name('semanticMissingCount', symbol_name)}:0:0;",
                    f"put_utility 'log' / '  ambiguous=' {_role_scalar_name('semanticAmbiguousCount', symbol_name)}:0:0;",
                    "",
                ]
            )

    declaration_output_path.write_text("\n".join(declaration_lines), encoding="utf-8")
    runtime_output_path.write_text("\n".join(runtime_lines), encoding="utf-8")


def _write_structured_symbol_includes(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    declaration_output_path: Path,
    assignment_output_path: Path,
) -> None:
    """Generate optional direct structured parameter declarations and assignments."""
    declaration_lines: list[str] = [
        "* Auto-generated structured symbol declarations for the current import basket.",
        "* Structured symbols are additive. Generic imports remain available for every job.",
        "",
    ]
    assignment_lines: list[str] = [
        "* Auto-generated structured symbol assignments for the current import basket.",
        "* Structured symbols are created only when index and value columns were supplied explicitly.",
        "",
    ]

    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        index_columns, value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )

        if not index_columns or not value_columns:
            assignment_lines.extend(
                [
                    f"* Structured symbol generation skipped for {symbol_name}: no explicit index/value structure supplied.",
                    f"put_utility 'log' / 'STRUCTURED_SYMBOL_SKIPPED: {symbol_name}';",
                    "",
                ]
            )
            continue

        table_name = _safe_gams_description(materialized_job.job.table_name)
        declaration_lines.append(f"* Structured symbols for {symbol_name} from {table_name}")
        for position, column_name in enumerate(index_columns, start=1):
            unique_labels = [
                f"'{_safe_gams_label(raw_value)}'"
                for raw_value in materialized_job.dataframe[column_name].drop_duplicates()
            ]
            declaration_lines.append(
                f'Set {_structured_index_set_name(symbol_name, position)}(*) '
                f'"structured index set {position} from column {column_name} for {symbol_name}" '
                f"/ {', '.join(unique_labels)} /;"
            )

        for value_column in value_columns:
            structured_name = _structured_parameter_name(symbol_name, value_column)
            domains = ", ".join(
                f"{_structured_index_set_name(symbol_name, position)}"
                for position in range(1, len(index_columns) + 1)
            )
            declaration_lines.append(
                f'Parameter {structured_name}({domains}) '
                f'"structured parameter derived from value column {value_column} for {symbol_name}";'
            )
        declaration_lines.append("")

        assignment_lines.append(
            f"put_utility 'log' / 'STRUCTURED_SYMBOL_READY: {symbol_name} indexes -> {', '.join(index_columns)}; values -> {', '.join(value_columns)}';"
        )

        for row in materialized_job.dataframe.itertuples(index=False, name=None):
            row_mapping = dict(zip(materialized_job.dataframe.columns, row, strict=True))
            index_labels = ", ".join(
                f"'{_safe_gams_label(row_mapping[column_name])}'"
                for column_name in index_columns
            )
            for value_column in value_columns:
                value = row_mapping[value_column]
                if pd.isna(value):
                    continue
                structured_name = _structured_parameter_name(symbol_name, value_column)
                assignment_lines.append(
                    f"{structured_name}({index_labels}) = {float(value)};"
                )
        assignment_lines.append("")

    declaration_output_path.write_text("\n".join(declaration_lines), encoding="utf-8")
    assignment_output_path.write_text("\n".join(assignment_lines), encoding="utf-8")


def _write_unload_include(
    jobs: list[MaterializedImportJob], validated_symbols: list[str], output_path: Path
) -> None:
    """Generate the list of imported and semantic symbols for execute_unload."""
    lines: list[str] = []
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        index_columns, value_columns = validate_structured_columns(
            materialized_job.dataframe,
            materialized_job.job.selected_columns,
            materialized_job.job.structured_index_columns,
            materialized_job.job.structured_value_columns,
        )
        lines.extend(
            [
                f"    {_obs_set_name(symbol_name)}",
                f"    {_col_set_name(symbol_name)}",
                f"    {symbol_name}",
                f"    {_role_assignment_set_name(symbol_name)}",
                f"    {_role_request_set_name(symbol_name)}",
                f"    {_role_materialized_set_name(symbol_name)}",
                f"    {_role_match_count_name(symbol_name)}",
                f"    {_role_value_name(symbol_name)}",
            ]
        )
        for role in SEMANTIC_ROLES:
            if role == "index":
                continue
            lines.append(f"    {role}__{symbol_name}")
        for position in range(1, len(index_columns) + 1):
            lines.append(f"    {_structured_index_set_name(symbol_name, position)}")
        for value_column in value_columns:
            lines.append(f"    {_structured_parameter_name(symbol_name, value_column)}")
        lines.extend(
            [
                f"    {_role_scalar_name('semanticMappingReady', symbol_name)}",
                f"    {_role_scalar_name('semanticMissingCount', symbol_name)}",
                f"    {_role_scalar_name('semanticAmbiguousCount', symbol_name)}",
            ]
        )
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
