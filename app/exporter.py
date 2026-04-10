"""Data export helpers for preview CSV and reusable GAMS symbol handoff."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

from .models import ExportArtifacts, MaterializedImportJob


PREVIEW_FILENAME = "exported_preview.csv"
LONG_FILENAME = "exported_data_long.csv"
IMPORT_JOB_DIRNAME = "import_jobs"
MANIFEST_FILENAME = "import_jobs_manifest.csv"
GENERATED_RUNTIME_INCLUDE = "generated_import_runtime.gms"
GENERATED_SYMBOL_INCLUDE = "generated_import_symbols.gms"
GENERATED_EXAMPLE_MODEL = "example_use_imported_symbols.gms"
GENERATED_UNLOAD_INCLUDE = "generated_unload_symbols.gms"

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

    preview_csv = save_preview_csv(jobs[0].dataframe, output_dir)
    legacy_long_csv = save_long_csv(jobs[0].dataframe, output_dir)
    manifest_csv = _write_manifest(jobs, output_dir / MANIFEST_FILENAME)
    _write_job_csvs(jobs, validated_symbols, job_directory)

    generated_runtime_include = gams_dir / GENERATED_RUNTIME_INCLUDE
    generated_symbol_include = gams_dir / GENERATED_SYMBOL_INCLUDE
    generated_example_model = gams_dir / GENERATED_EXAMPLE_MODEL
    generated_unload_include = gams_dir / GENERATED_UNLOAD_INCLUDE

    _write_runtime_include(jobs, validated_symbols, generated_runtime_include)
    _write_unload_include(validated_symbols, generated_unload_include)
    _write_symbol_include(jobs, validated_symbols, generated_symbol_include)
    _write_example_consumer(jobs, validated_symbols, generated_example_model)

    return ExportArtifacts(
        preview_csv=preview_csv,
        legacy_long_csv=legacy_long_csv,
        job_directory=job_directory,
        manifest_csv=manifest_csv,
        generated_runtime_include=generated_runtime_include,
        generated_symbol_include=generated_symbol_include,
        generated_example_model=generated_example_model,
        generated_unload_include=generated_unload_include,
        symbol_names=validated_symbols,
        primary_symbol_name=validated_symbols[0],
    )


def _write_manifest(jobs: list[MaterializedImportJob], output_path: Path) -> Path:
    """Write a CSV manifest describing the queued import jobs."""
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["symbol_name", "table_name", "selected_columns", "max_rows", "where_clause"]
        )
        for materialized_job in jobs:
            writer.writerow(
                [
                    materialized_job.job.symbol_name,
                    materialized_job.job.table_name,
                    ",".join(materialized_job.job.selected_columns),
                    materialized_job.job.max_rows,
                    materialized_job.job.where_clause,
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


def _obs_set_name(symbol_name: str) -> str:
    return f"obs__{symbol_name}"


def _col_set_name(symbol_name: str) -> str:
    return f"col__{symbol_name}"


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


def _write_unload_include(validated_symbols: list[str], output_path: Path) -> None:
    """Generate the list of dynamically imported symbols for execute_unload."""
    lines: list[str] = []
    for symbol_name in validated_symbols:
        lines.extend(
            [
                f"    {_obs_set_name(symbol_name)}",
                f"    {_col_set_name(symbol_name)}",
                f"    {symbol_name}",
            ]
        )
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_symbol_include(
    jobs: list[MaterializedImportJob],
    validated_symbols: list[str],
    output_path: Path,
) -> None:
    """Generate a consumer-friendly include for loading imported symbols from GDX."""
    lines: list[str] = [
        "* Auto-generated helper include for loading imported SQL symbols into your own GAMS model.",
        "* Include this file after the import pipeline has created data/imported_data.gdx.",
        "",
        "Sets",
        '    obs(*) "primary observation set from the first import job"',
        '    col(*) "primary column set from the first import job"',
    ]
    for symbol_name in validated_symbols:
        lines.append(f'    {_obs_set_name(symbol_name)}(*) "observation set for {symbol_name}"')
        lines.append(f'    {_col_set_name(symbol_name)}(*) "column set for {symbol_name}"')
    lines[-1] = lines[-1] + ";"

    lines.extend(["", "Parameters", '    data(obs<, col<) "backward-compatible primary imported symbol"'])
    for materialized_job, symbol_name in zip(jobs, validated_symbols, strict=True):
        description = _safe_gams_description(
            f"imported numeric data from {materialized_job.job.table_name}"
        )
        lines.append(
            f'    {symbol_name}({_obs_set_name(symbol_name)}<, {_col_set_name(symbol_name)}<) "{description}"'
        )
    lines[-1] = lines[-1] + ";"

    lines.extend(["", "$gdxin data/imported_data.gdx", "$load data"])
    for symbol_name in validated_symbols:
        lines.append(f"$load {symbol_name}")
    lines.extend(["$gdxin", ""])

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

    display_items = ["data", "totalPrimaryData", *validated_symbols[:2]]
    display_items.extend(f"total__{symbol_name}" for symbol_name in validated_symbols[:2])
    lines.append("display " + ", ".join(display_items) + ";")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
