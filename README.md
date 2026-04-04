# MySQL to GAMS Importer

`gams-mysql-importer` is a Windows-oriented Python desktop application that lets a user connect to a MySQL database, inspect tables and columns, preview a bounded subset of rows, export numeric data into a GAMS-friendly long CSV format, and then launch a GAMS model automatically.

The project is designed as a clean front-end around a GAMS Connect workflow. The Python GUI handles selection, validation, preview, export, and subprocess execution, while the GAMS model imports the exported CSV and performs a simple summary analysis.

## Project Purpose

This repository provides a professional desktop front-end for workflows where database data must be inspected by a user before being passed into GAMS for optimization or analytical preprocessing. It is especially useful when:

- the user needs to browse tables and columns interactively,
- only a selected subset of rows should be imported,
- data should be exported in a controlled and reproducible format,
- the final step should trigger a GAMS model automatically.

## Architecture Overview

The application is split into small modules:

- `app/gui_importer.py`: tkinter desktop window and user interaction flow.
- `app/db.py`: SQLAlchemy and PyMySQL access layer for MySQL metadata and preview queries.
- `app/exporter.py`: preview CSV export and conversion to the required `obs, column_name, value` long format.
- `app/runner.py`: subprocess wrapper for calling GAMS.
- `app/utils.py`: configuration loading and logging setup.
- `gams/model.gms`: GAMS Connect model that imports the exported long CSV.

High-level flow:

1. Load database settings from `config/db_config.json` if available, otherwise from `config/db_config.example.json`.
2. Connect to MySQL.
3. Read available tables from `information_schema.tables`.
4. Read column names from `information_schema.columns`.
5. Preview user-selected data with a `LIMIT`.
6. Save preview data to `data/exported_preview.csv`.
7. Convert numeric columns to long format and save `data/exported_data_long.csv`.
8. Call `gams gams/model.gms`.

## Folder Structure

```text
gams-mysql-importer/
├── app/
│   ├── __init__.py
│   ├── db.py
│   ├── exporter.py
│   ├── gui_importer.py
│   ├── runner.py
│   └── utils.py
├── config/
│   └── db_config.example.json
├── data/
│   └── .gitkeep
├── gams/
│   └── model.gms
├── scripts/
│   ├── run_app.bat
│   └── setup_windows.ps1
├── tests/
│   └── test_exporter.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Prerequisites

- Windows 10 or Windows 11
- Python 3.11
- Access to the target MySQL database
- GAMS installed locally and accessible from the command line as `gams`

## Windows Setup

From PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

This script creates a `.venv` virtual environment and installs dependencies from `requirements.txt`.

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

## How GAMS Is Called

When the user previews data and then chooses `Export and Run GAMS`, the application:

- writes `data/exported_preview.csv`,
- writes `data/exported_data_long.csv`,
- runs the equivalent of:

```powershell
gams gams/model.gms
```

If GAMS is missing from `PATH` or the run fails, the application shows a friendly error dialog with execution details.

## Data Export Rules

- Preview data is always saved to `data/exported_preview.csv`.
- Only numeric columns are exported for GAMS.
- Numeric data is transformed into long format with exactly these columns:
  - `obs`
  - `column_name`
  - `value`
- Observation numbering starts at `1`.
- If the selected preview contains no numeric columns, the GUI shows an error and GAMS is not launched.

## Current Assumptions and Limitations

- Table and column names are validated conservatively for safe identifier quoting.
- The GUI is intended for moderate interactive preview sizes rather than very large extracts.
- The GAMS model currently computes a simple mean by numeric column and displays imported dimensions.
- Local verification of the GAMS run requires a working GAMS installation on the machine.
- The application previews first, then exports from the previewed data currently held in memory.

## Future Extension Ideas

- Persist the last selected table and columns between sessions.
- Add schema selection for multi-schema MySQL installations.
- Support richer type-aware export mappings beyond numeric long-format output.
- Add progress indicators for larger preview operations.
- Add automated integration tests against a disposable MySQL instance.
- Generate GDX or alternative GAMS input formats when required by a larger model.
