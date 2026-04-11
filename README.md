# MySQL to GAMS Importer

`gams-mysql-importer` is a Windows-oriented Python desktop application that turns user-selected MySQL data into reusable GAMS symbols. The application lets a user queue one or more SQL import jobs, preview the current selection, export numeric columns into a professional GAMS handoff, run GAMS automatically, and inspect the resulting `.gdx`, listing, and log artifacts in GAMS Studio.

The current architecture supports two layers at the same time:

- a backward-compatible primary symbol `data(obs,col)` for the first queued import job,
- reusable named symbols such as `certificationData(obs,col)` and `laborCostData(obs,col)` that can be loaded later in arbitrary GAMS scripts.

Phase 3 adds an optional third layer when the user provides enough structure information:

- direct derived parameters such as `productsData__profit(i)` or `arcData__cost(i,j)` built from explicit index and value column choices.

Phase 4 adds a fourth usability layer for downstream modeling:

- generated helper artifacts that explain how multiple imported jobs fit together in one GAMS model.

## Motivation And Problem Solved

Traditional SQL-to-GAMS workflows often leave too much manual work between data selection and model execution:

- SQL queries are edited by hand for each scenario,
- imported data is tied too tightly to one specific GAMS script,
- there is no stable artifact for later reuse in other models,
- end users have limited confidence about what was imported and where it ended up.

This project solves that by creating a repeatable bridge:

- the user prepares imports interactively in a GUI,
- the application exports named reusable symbols,
- GAMS stores those symbols in `imported_data.gdx`,
- later GAMS models can load the same symbols directly without rerunning the SQL logic manually.

## Project Purpose

This repository provides a professional desktop front-end for workflows where SQL data must be curated interactively before being reused in GAMS for calculations, reporting, or optimization. It is useful when:

- the user needs to browse tables and columns interactively,
- multiple import jobs should be prepared before the GAMS run,
- imported data should be preserved as named reusable symbols,
- the resulting symbols should be available in a `.gdx` database for later models,
- optional demo optimization should remain available without constraining the broader workflow.

## Architecture Overview

The application is split into small modules:

- `app/gui_importer.py`: tkinter desktop window, preview logic, and import basket workflow.
- `app/db.py`: SQLAlchemy and PyMySQL access layer for MySQL metadata, previews, and simple filters.
- `app/exporter.py`: multi-job export pipeline, GAMS symbol validation, CSV generation, and generated include files.
- `app/models.py`: shared dataclasses for queued import jobs and generated artifacts.
- `app/runner.py`: subprocess wrapper for calling GAMS and opening GAMS Studio.
- `app/utils.py`: configuration loading and logging setup.
- `gams/model.gms`: main GAMS entry point for generated imports, semantic mapping, and optional demo optimization.
- `gams/import_mapping.gms`: semantic mapping from imported column names to optional model-ready parameters.
- `gams/optimization_example.gms`: optional resource-allocation LP example using the mapped primary symbol.
- `gams/example_use_imported_symbols.gms`: separate GAMS consumer script showing how imported symbols can be reused.
- `gams/example_use_structured_symbols.gms`: separate GAMS consumer script showing how direct structured symbols can be reused.
- `gams/example_multi_job_integration.gms`: generated downstream example showing how multiple imported jobs can be combined in one model.

High-level flow:

1. Load database settings from `config/db_config.json` if available, otherwise from `config/db_config.example.json`.
2. Connect to MySQL.
3. Read available tables from `information_schema.tables`.
4. Read column names from `information_schema.columns`.
5. Preview the current import selection with a `LIMIT` and optional simple filter.
6. Add one or more validated import jobs to the basket.
7. On execution, fetch each queued job and export one long-format CSV per output symbol.
8. Generate GAMS include files that declare and document the imported symbols for the current run.
9. Run `gams gams/model.gms`.
10. Save all imported symbols to `data/imported_data.gdx` for reuse in other GAMS scripts.

## Advanced Workflow Summary

The advanced branch now supports one coherent workflow across Phases 1 through 4:

1. Build one or more import jobs in the GUI.
2. Validate each job through the `Pre-Run Readiness` panel.
3. Optionally assign semantic roles such as `profit`, `capacity`, or `cost`.
4. Optionally define structured index and value columns for direct GAMS parameters.
5. Export the full basket and run GAMS once.
6. Inspect the resulting artifacts in the `Post-Run Results` panel, GAMS Studio, `data/import_jobs_manifest.csv`, and `data/imported_symbol_catalog.csv`.
7. Reuse the generated symbols in downstream GAMS models through:
   - generic symbols for flexible inspection,
   - semantic symbols for observation-based model meaning,
   - structured symbols for direct model-ready coefficients,
   - multi-job helper artifacts for combining multiple imported jobs cleanly.

## Folder Structure

```text
gams-mysql-importer/
|-- app/
|   |-- __init__.py
|   |-- __main__.py
|   |-- db.py
|   |-- exporter.py
|   |-- gui_importer.py
|   |-- models.py
|   |-- runner.py
|   `-- utils.py
|-- config/
|   `-- db_config.example.json
|-- data/
|   `-- .gitkeep
|-- gams/
|   |-- example_use_imported_symbols.gms
|   |-- example_use_structured_symbols.gms
|   |-- import_mapping.gms
|   |-- model.gms
|   |-- optimization_example.gms
|   `-- sample_optimization_long.csv
|-- scripts/
|   |-- run_app.bat
|   `-- setup_windows.ps1
|-- tests/
|   |-- test_db.py
|   `-- test_exporter.py
|-- .gitignore
|-- README.md
`-- requirements.txt
```

Generated at runtime:

- `data/import_jobs/<symbol>.csv`
- `data/import_jobs_manifest.csv`
- `data/imported_data.gdx`
- `data/gams_run.lst`
- `data/gams_run.log`
- `gams/generated_import_runtime.gms`
- `gams/generated_import_symbols.gms`
- `gams/generated_modeling_helpers.gms`
- `gams/generated_unload_symbols.gms`
- `gams/generated_structured_declarations.gms`
- `gams/generated_structured_assignments.gms`
- `gams/example_multi_job_integration.gms`
- `gams/example_use_imported_symbols.gms` may be refreshed to reflect the current basket

## Prerequisites

- Windows 10 or Windows 11
- Python 3.11
- Access to the target MySQL database
- GAMS installed locally
- A MySQL account with permission to read the selected tables

## Windows Setup

From PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

This script creates a `.venv` virtual environment and installs dependencies from `requirements.txt`. It prefers Python 3.11 through the Windows `py` launcher and recreates `.venv` if the existing interpreter version is wrong.

## Python Environment Setup

The recommended local workflow is:

```powershell
cd C:\Users\Akhan\Desktop\gams-mysql-importer
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe --version
```

You should see `Python 3.11.x`.

## Database Configuration

1. Copy `config/db_config.example.json` to `config/db_config.json`.
2. Replace the placeholder values with your real database settings.
3. Keep `config/db_config.json` local only; it is ignored by git.

Example:

```json
{
  "host": "160.78.47.10",
  "port": 3306,
  "database": "RICA",
  "user": "usergams",
  "password": "your-real-password"
}
```

Configuration behavior:

- The app reads `config/db_config.json` first if it exists.
- If it does not exist, the app falls back to `config/db_config.example.json`.
- A warning is shown in the GUI when the example config is being used.

## Running the GUI

After setup:

```powershell
.\.venv\Scripts\python.exe -m app.gui_importer
```

Or double-click:

```text
scripts\run_app.bat
```

The window title is `MySQL to GAMS Importer`.

## GUI Workflow

1. Click `Connect to Database`.
2. Choose the source table for the current import job.
3. Select one or more columns.
4. Provide:
   - `Output symbol`
   - `Max rows`
   - optional `Filter expression`
5. Optionally assign semantic roles to selected columns:
   - `index`
   - `profit`
   - `capacity`
   - `demand`
   - `cost`
   - `lower_bound`
   - `upper_bound`
6. Click `Assign Role To Selected Columns` to record the current semantic choices.
7. Optionally define direct structure for the current basket item:
   - mark one or two columns as structured indexes
   - mark one or more numeric columns as structured values
8. Review the `Pre-Run Readiness` panel to confirm:
   - selected table
   - selected columns
   - symbol name
   - row limit
   - filter
   - structured index columns
   - structured value columns
   - whether the current selection includes at least one numeric column
9. Click `Preview Current Selection` if you want to inspect the current form.
10. Click `Add Import Job` to place the current selection in the import basket.
11. Use `Load Selected Item Into Form`, `Update Selected Basket Item`, or `Duplicate Selected Basket Item` to refine basket entries without rebuilding them from scratch.
12. Repeat for additional tables or symbol names.
13. Review the `Import Basket`.
14. Click `Export Basket and Run GAMS`.

Professional behavior of the basket:

- each job has its own source table, selected columns, row limit, filter text, and output symbol,
- each job can also carry optional per-column semantic role assignments,
- each job can also carry optional structured index and value assignments for direct parameter generation,
- basket items can be loaded back into the form for editing and duplicated with a safe new symbol name,
- the first queued job becomes the backward-compatible primary symbol `data(obs,col)`,
- every queued job also produces its own reusable named symbol,
- a structured basket item can also produce direct one- or two-dimensional GAMS parameters.

## Generated Outputs And Artifacts

The most important generated artifact is:

- `data/imported_data.gdx`

This is the GAMS-side handoff artifact for the whole run.

Other important runtime outputs:

- `data/exported_preview.csv`
- `data/exported_data_long.csv`
- `data/import_jobs/<symbol>.csv`
- `data/import_jobs_manifest.csv`
- `data/imported_symbol_catalog.csv`
- `data/gams_run.lst`
- `data/gams_run.log`
- `gams/generated_import_runtime.gms`
- `gams/generated_import_symbols.gms`
- `gams/generated_modeling_helpers.gms`
- `gams/generated_semantic_declarations.gms`
- `gams/generated_semantic_mapping.gms`
- `gams/generated_structured_declarations.gms`
- `gams/generated_structured_assignments.gms`
- `gams/generated_unload_symbols.gms`
- GUI `Pre-Run Readiness` panel
- GUI `Post-Run Results` panel

Meaning of the key files:

- `imported_data.gdx`: reusable GAMS database containing all imported symbols
- `generated_import_runtime.gms`: generated import declarations and Connect block for the current run
- `generated_import_symbols.gms`: helper include for later `$gdxin` / `$load`
- `generated_modeling_helpers.gms`: generated job catalog and symbol mapping helper for downstream multi-job models
- `generated_semantic_declarations.gms`: generated declarations for per-job semantic role symbols
- `generated_semantic_mapping.gms`: generated semantic role assignments and mapped per-job parameters
- `generated_structured_declarations.gms`: generated declarations for direct structured sets and parameters
- `generated_structured_assignments.gms`: generated assignments for direct structured parameters
- `generated_unload_symbols.gms`: generated unload list used by the main model
- `gams_run.lst`: listing file for inspecting execution details
- `gams_run.log`: log file for a concise execution trace
- `import_jobs_manifest.csv`: job-level summary showing generic, semantic, and structured outputs for each queued import
- `imported_symbol_catalog.csv`: row-per-symbol catalog for downstream modeling and debugging
- `Pre-Run Readiness`: form-level summary that helps catch missing numeric columns and filter issues before export
- `Post-Run Results`: artifact inventory with the main output file paths from the latest run

## How GAMS Is Called

When the user executes the basket, the application:

- writes `data/exported_preview.csv` for the first queued job,
- writes `data/exported_data_long.csv` for the first queued job to preserve backward compatibility,
- writes one long-format CSV per queued symbol under `data/import_jobs/`,
- generates GAMS helper include files for the current run,
- generates semantic role includes for any queued jobs that have role assignments,
- generates structured symbol includes for any queued jobs that have explicit index/value structure,
- runs the equivalent of:

```powershell
gams gams/model.gms
```

On a successful run, the application also creates:

- `data/imported_data.gdx`
- `data/gams_run.lst`
- `data/gams_run.log`

GAMS Studio is opened automatically when available.

## How To Inspect `imported_data.gdx`

There are two recommended inspection paths:

1. Open the run in GAMS Studio after export. The application tries to do this automatically.
2. Open `data/imported_data.gdx` in GAMS Studio manually and inspect:
   - symbol names
   - dimensions
   - domain labels
   - loaded values

This is the best way to confirm exactly what the SQL import produced before using the data in downstream models.

## Data Export Rules

- Preview data is saved to `data/exported_preview.csv` for the first queued job.
- The backward-compatible legacy export is still written to `data/exported_data_long.csv` for the first queued job.
- Each queued import job is exported as a long-format numeric CSV:
  - `obs`
  - `column_name`
  - `value`
- Observation numbering starts at `1` independently for each import job.
- Only numeric columns are exported into GAMS parameters.
- If a queued job contains no numeric columns in the fetched result, the export fails clearly before GAMS runs.

## Validation And Safety Notes

- Output symbol names must start with a letter or underscore and may contain only letters, digits, and underscores.
- Reserved names such as `data`, `obs`, `col`, `profit`, and `capacity` cannot be used as output symbols.
- The GUI validates table and column choices before adding or updating a basket item.
- The `Filter expression` field is intentionally conservative:
  - use only a simple filter expression such as `Anno = 2023` or `profit > 0`
  - semicolons, SQL comments, joins, unions, and full SQL statements are blocked
- The pre-run validation step checks that each queued import job still has at least one numeric column selected before GAMS is started.
- Structured generation is opt-in and only activates when both of these are true:
  - at least one structured index column is selected
  - at least one numeric structured value column is selected
- Structured generation currently supports up to two index columns for direct `param(i)` and `param(i,j)` style outputs.

## End-To-End Example

The example below shows the full Phase 1 plus Phase 2 plus Phase 3 workflow in one pass.

### In the GUI

1. Click `Connect to Database`.
2. Select table `PRODUCTS`.
3. Select columns `sku`, `profit`, and `capacity`.
4. Enter:
   - `Output symbol`: `productsData`
   - `Max rows`: `25`
   - `Filter expression`: `profit > 0`
5. Assign semantic roles:
   - `sku` -> `index`
   - `profit` -> `profit`
   - `capacity` -> `capacity`
6. Assign direct structure:
   - structured index columns: `sku`
   - structured value columns: `profit`, `capacity`
7. Confirm in `Pre-Run Readiness` that:
   - the selected table is `PRODUCTS`
   - the selected columns are correct
   - the symbol name is `productsData`
   - the structured index column is `sku`
   - the structured value columns are `profit`, `capacity`
   - numeric columns are present
8. Click `Add Import Job`.
9. Click `Export Basket and Run GAMS`.

### What the run creates

After a successful run, the most important outputs are:

- `data/imported_data.gdx`
- `gams/generated_import_symbols.gms`
- `gams/generated_semantic_mapping.gms`
- `gams/generated_structured_declarations.gms`
- `gams/generated_structured_assignments.gms`
- `data/gams_run.lst`
- `data/gams_run.log`

On the GAMS side, this single basket item gives you:

- `data(obs,col)` because it is the first queued job
- `productsData(obs__productsData,col__productsData)` as the reusable named symbol
- `profit__productsData(obs__productsData)`
- `capacity__productsData(obs__productsData)`
- `productsData__profit(structuredIndex1__productsData)`
- `productsData__capacity(structuredIndex1__productsData)`

### In a downstream GAMS script

You can then load and use the generated symbols in a separate model:

```gams
Sets
    obs__productsData(*)
    col__productsData(*)
    structuredIndex1__productsData(*);

Parameters
    productsData(obs__productsData<, col__productsData<)
    profit__productsData(obs__productsData<)
    capacity__productsData(obs__productsData<)
    productsData__profit(structuredIndex1__productsData)
    productsData__capacity(structuredIndex1__productsData);

$gdxin data/imported_data.gdx
$load productsData
$load profit__productsData
$load capacity__productsData
$load structuredIndex1__productsData
$load productsData__profit
$load productsData__capacity
$gdxin

display productsData, profit__productsData, capacity__productsData, productsData__profit, productsData__capacity;
```

This is the intended bridge:

- the GUI prepares a safe import basket,
- GAMS receives reusable symbols,
- GAMS also receives direct structured parameters when the basket item was explicitly structured,
- downstream GAMS code loads those symbols from `imported_data.gdx` without repeating the SQL selection logic.

## How To Use Imported SQL Data In Your Own GAMS Model

This is the core reusable bridge.

### When to use generic vs semantic vs structured

Use the three symbol layers for different modeling situations:

- `generic`
  Use when you want maximum flexibility or when the data structure is still exploratory.
  Example: `productsData(obs,col)`
- `semantic`
  Use when a basket item has clear economic or modeling meaning such as `profit`, `capacity`, or `cost`, but you still want an observation-based view.
  Example: `profit__productsData(obs__productsData)`
- `structured`
  Use when you explicitly know the index columns and want direct model-ready parameters such as `param(i)` or `param(i,j)`.
  Example: `productsData__profit(structuredIndex1__productsData)`

The recommended workflow is:

1. Start with generic imports for safety and traceability.
2. Add semantic roles when the columns have stable meaning.
3. Add structured index/value assignments when you want direct downstream model coefficients.
4. Use the Phase 4 helper artifacts when you want to combine two or more imported jobs in one downstream model.

### Layering at a glance

For each queued basket item, the generated outputs now fit into four practical layers:

- `generic imported symbols`
  Example: `productsData(obs,col)`
  Use these when the imported data should stay close to the original SQL selection.
- `semantic derived symbols`
  Example: `profit__productsData(obs__productsData)`
  Use these when selected columns have stable business or optimization meaning, but you still want an observation-based structure.
- `structured derived symbols`
  Example: `productsData__profit(structuredIndex1__productsData)`
  Use these when you explicitly know the desired direct model dimensions.
- `multi-job downstream integration artifacts`
  Examples: `gams/generated_modeling_helpers.gms`, `data/import_jobs_manifest.csv`, `data/imported_symbol_catalog.csv`
  Use these when you want to understand and combine multiple imported jobs in one model without guessing what was generated.

### How imported symbols are named

Each queued import job has an explicit `Output symbol` in the GUI. If the user chooses:

- `certificationData`
- `laborCostData`

then the GAMS run creates reusable symbols:

- `certificationData(obs,col)`
- `laborCostData(obs,col)`

The first queued job is also exposed as:

- `data(obs,col)`

for backward compatibility with the earlier workflow and the optional semantic mapping demo.

### Where `imported_data.gdx` is written

The reusable GDX file is written to:

- `data/imported_data.gdx`

This file contains:

- the backward-compatible `data(obs,col)` symbol,
- one named symbol per queued import job,
- the supporting observation and column sets for those symbols,
- the optional semantic mapping and demo optimization symbols.

### How to load symbols using `$gdxin` and `$load`

The recommended path is to include the generated helper:

```gams
$include "gams/generated_import_symbols.gms"
```

That generated include:

- declares the current imported symbols,
- points to `data/imported_data.gdx`,
- loads the current symbols automatically.

You can also load them manually:

```gams
Sets
    obs__productsData(*)
    col__productsData(*);

Parameters
    productsData(obs__productsData<, col__productsData<);

$gdxin data/imported_data.gdx
$load productsData
$gdxin

display productsData;
```

The same pattern works for two or more imported symbols:

```gams
Sets
    obs__productsData(*)
    col__productsData(*)
    obs__resourcesData(*)
    col__resourcesData(*);

Parameters
    productsData(obs__productsData<, col__productsData<)
    resourcesData(obs__resourcesData<, col__resourcesData<);

$gdxin data/imported_data.gdx
$load productsData
$load resourcesData
$gdxin

display productsData, resourcesData;
```

## Structured Symbol Generation

Phase 3 adds an opt-in direct-structure layer on top of the generic imports.

If the user explicitly assigns:

- one or two structured index columns
- one or more structured numeric value columns

then the exporter generates direct GAMS parameters in addition to the generic fallback symbol.

For example, if a basket item is configured as:

- table: `PRODUCTS`
- selected columns: `sku`, `profit`, `capacity`
- output symbol: `productsData`
- structured index columns: `sku`
- structured value columns: `profit`, `capacity`

then the run still creates the generic symbol:

- `productsData(obs__productsData,col__productsData)`

and also creates direct structured parameters:

- `productsData__profit(structuredIndex1__productsData)`
- `productsData__capacity(structuredIndex1__productsData)`

If a basket item uses two structured index columns, the generated direct parameter becomes two-dimensional, for example:

- `arcData__cost(structuredIndex1__arcData, structuredIndex2__arcData)`

Important behavior:

- generic imports are always preserved
- structured generation is opt-in
- structured generation is currently limited to one or two index columns
- structured value columns must be numeric
- if structured information is incomplete, the generic symbol still works and the structured layer is skipped safely

### Example structured load in downstream GAMS

```gams
Sets
    structuredIndex1__productsData(*);

Parameters
    productsData__profit(structuredIndex1__productsData)
    productsData__capacity(structuredIndex1__productsData);

$gdxin data/imported_data.gdx
$load structuredIndex1__productsData
$load productsData__profit
$load productsData__capacity
$gdxin

display productsData__profit, productsData__capacity;
```

## Combining Multiple Imported Jobs In One GAMS Model

Phase 4 focuses on making multi-job downstream models easier to understand and assemble.

For each run, the exporter now produces:

- `gams/generated_modeling_helpers.gms`
- `data/import_jobs_manifest.csv`
- `data/imported_symbol_catalog.csv`
- `gams/example_multi_job_integration.gms`

These help answer four common questions:

1. Which jobs were imported in this run?
2. Which generic symbols belong to each job?
3. Which semantic symbols were derived for each job?
4. Which structured symbols and dimensions were derived for each job?

### Generated multi-job helper include

`gams/generated_modeling_helpers.gms` declares small helper sets and parameters such as:

- `importJob`
- `genericImportedSymbol(importJob,*)`
- `semanticDerivedSymbol(importJob,*)`
- `structuredIndexSet(importJob,*)`
- `structuredDerivedSymbol(importJob,*)`
- `sharedDimensionLabel(importJob,*)`
- `structuredRank(importJob)`
- `semanticRoleCount(importJob)`
- `structuredValueCount(importJob)`

These are designed for downstream inspection and documentation, not as a replacement for the imported symbols themselves.

### Example: combining two jobs

Suppose the current run produced:

- `productsData`
- `arcData`

Then a downstream model can load both the symbols and the helper catalog:

```gams
$include "gams/generated_import_symbols.gms"
$include "gams/generated_modeling_helpers.gms"

Scalar totalProducts;
Scalar totalArcs;
Scalar totalProfit;
Scalar totalArcCost;

totalProducts = sum((obs__productsData, col__productsData), productsData(obs__productsData, col__productsData));
totalArcs = sum((obs__arcData, col__arcData), arcData(obs__arcData, col__arcData));
totalProfit = sum(structuredIndex1__productsData, productsData__profit(structuredIndex1__productsData));
totalArcCost = sum((structuredIndex1__arcData, structuredIndex2__arcData), arcData__cost(structuredIndex1__arcData, structuredIndex2__arcData));

display
    importJob,
    genericImportedSymbol,
    semanticDerivedSymbol,
    structuredDerivedSymbol,
    sharedDimensionLabel,
    totalProducts,
    totalArcs,
    totalProfit,
    totalArcCost;
```

This example intentionally combines:

- generic imported symbols from two jobs
- one structured parameter from the first job
- one structured parameter from the second job

The generated file `gams/example_multi_job_integration.gms` provides the same pattern for the current basket.

### Naming convention summary

The current naming scheme is designed to be predictable:

- generic symbol: `<symbolName>(obs,col)`
- semantic symbol: `<role>__<symbolName>(obs__<symbolName>)`
- structured symbol: `<symbolName>__<valueColumn>(structuredIndex1__<symbolName>, ...)`
- multi-job helper files:
  - `gams/generated_modeling_helpers.gms`
  - `data/import_jobs_manifest.csv`
  - `data/imported_symbol_catalog.csv`

This keeps the original import identity visible while still making derived symbols easy to recognize in GAMS Studio and downstream scripts.

## Semantic Role Assignment

Phase 2 adds an optional semantic layer on top of the reusable generic imports.

In the GUI, selected columns for each import job can now be tagged with roles such as:

- `index`
- `profit`
- `capacity`
- `demand`
- `cost`
- `lower_bound`
- `upper_bound`

These assignments are stored per queued job and exported into generated runtime files:

- `gams/generated_semantic_declarations.gms`
- `gams/generated_semantic_mapping.gms`

For a queued job with output symbol `productsData`, the generated GAMS layer now produces:

- `requestedSemanticColumn__productsData(semanticRole,*)`
- `requestedSemanticRole__productsData(semanticRole)`
- `semanticColumn__productsData(semanticRole,col__productsData)`
- `semanticValue__productsData(obs__productsData,semanticRole)`
- `profit__productsData(obs__productsData)`
- `capacity__productsData(obs__productsData)`
- `cost__productsData(obs__productsData)`
- `demand__productsData(obs__productsData)`
- `lower_bound__productsData(obs__productsData)`
- `upper_bound__productsData(obs__productsData)`

Important behavior:

- generic named imports such as `productsData(obs,col)` always remain available,
- semantic mappings are optional and additive,
- incomplete semantic mappings do not block generic import,
- the backward-compatible primary symbol `data(obs,col)` is still preserved from the first queued job.

This means semantic role assignment is now available across queued import jobs, not only through the older primary-symbol demo path.

### How to use `execute_load`

If you prefer runtime loading:

```gams
execute_load 'data/imported_data.gdx', certificationData, laborCostData;
```

This is useful in models that open and close GDX files procedurally.

### How to inspect symbols in GAMS Studio

After a successful run, the application opens GAMS Studio on:

- the main model,
- the listing file,
- the generated GDX file.

You can inspect the symbols interactively in GAMS Studio to confirm:

- symbol names,
- dimensions,
- loaded records,
- set labels for observations and columns.

### How to extend the approach for custom optimization models

1. Queue and export the SQL data you need from the GUI.
2. Open `data/imported_data.gdx` or include `gams/generated_import_symbols.gms`.
3. Load the symbols relevant to your own model.
4. Build semantic parameters, index structures, or direct model coefficients from those imported symbols.
5. Reuse the current `gams/import_mapping.gms` and `gams/optimization_example.gms` only as optional examples, not as the required architecture.

The important design principle is that imported SQL data is now preserved as named reusable GAMS symbols first, and only then optionally interpreted for a particular optimization example.

## Backward Compatibility With `data(obs,col)`

To preserve earlier behavior, the first queued import job is also written as:

- `data(obs,col)`

This is useful for:

- existing scripts built around the earlier generic pipeline,
- the optional semantic mapping layer,
- the optional demo optimization example.

So the current system provides both:

- one stable generic primary symbol for compatibility,
- multiple named symbols for reusable downstream modeling.

## Optional Semantic Mapping And Demo Optimization

The repository still includes the earlier demo optimization as a professional example, but it is now optional.

- `gams/import_mapping.gms` maps selected column names from the primary symbol `data(obs,col)` into:
  - `profit(obs)`
  - `capacity(obs)`
  - `cost(obs)`
  - `demand(obs)`
- the generated Phase 2 semantic layer maps optional GUI-assigned roles for every queued job into job-specific symbols such as:
  - `profit__productsData(obs__productsData)`
  - `capacity__productsData(obs__productsData)`
  - `cost__resourcesData(obs__resourcesData)`
- `gams/optimization_example.gms` solves a small linear resource-allocation model if the required mapped fields are present.
- If the required mapped fields are not present, generic import still succeeds and the optimization example is skipped gracefully.

## Test Without The GUI

A small example CSV is included at `gams/sample_optimization_long.csv`.

To test the semantic mapping and optimization example quickly:

```powershell
Copy-Item .\gams\sample_optimization_long.csv .\data\exported_data_long.csv -Force
& 'C:\GAMS\53\gams.exe' .\gams\model.gms
```

For the full reusable-symbol workflow, use the GUI so that the generated import basket files are created.

## Testing And Verification

Recommended local checks:

```powershell
python -m compileall app tests
python -m pytest tests/test_exporter.py
```

Practical runtime verification:

1. Start the GUI.
2. Queue one or more import jobs.
3. Confirm the `Pre-Run Readiness` panel looks correct.
4. Run `Export Basket and Run GAMS`.
5. Confirm that:
   - `data/imported_data.gdx` exists
   - `data/gams_run.lst` exists
   - `data/gams_run.log` exists
   - generated helper files exist under `gams/`
6. Confirm the `Post-Run Results` panel lists the generated artifact locations.
7. Open or include `gams/generated_import_symbols.gms` from another GAMS script.

## Current Assumptions And Limitations

- Imported GAMS symbols are currently numeric parameter-style symbols in the standardized form `<symbolName>(obs,col)`.
- Direct structured generation currently supports one- and two-dimensional parameters only.
- The current `Filter expression` box supports only a conservative simple SQL filter expression; it is not a full SQL editor.
- The first queued job is treated as the backward-compatible primary symbol `data(obs,col)`.
- Semantic role assignment now works across queued jobs, but the older demo optimization still solves only from the backward-compatible primary symbol `data(obs,col)`.
- Direct automatic inference of richer structures such as `parameter cost(i,t)` without explicit structure choices is not yet implemented.
- Semantic roles remain user-assigned metadata; the project does not yet infer richer dimensions such as `cost(i,j)` automatically.
- Import jobs with nonnumeric selected results cannot currently become GAMS parameters.
- Local verification of the GAMS run requires a working GAMS installation on the machine.

## Notes On Security And Configuration Handling

- Real credentials belong only in `config/db_config.json`, which is ignored by git.
- `config/db_config.example.json` should keep placeholder values only.
- The filter box is intentionally conservative to reduce SQL misuse risk.
- Generated runtime files and exported data artifacts are ignored in `.gitignore` because they are transient per run.
- If credentials were ever pasted into logs or chats, rotate them before using the project further.

## Roadmap / Future Improvements

- Infer richer index/value structures automatically when a job clearly has identifier columns plus one value column.
- Extend direct structured generation beyond two index dimensions when a modeling workflow requires it.
- Externalize semantic role mapping to JSON or YAML configuration instead of the current generated GAMS include.
- Add per-job preview snapshots inside the basket.
- Add saved import basket templates for repeated data workflows.
- Add integration tests against a disposable MySQL instance.
