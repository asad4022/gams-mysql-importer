# MySQL to GAMS Importer

This repository is the first stable version of the MySQL-to-GAMS desktop importer. It is intended to be used from the local folder `C:\Users\Akhan\Desktop\gams-mysql-importer-first` on branch `codex/mysql-to-gams-importer`.

The goal of this version is to keep the original importer workflow intact while making it reliable on both Windows and macOS:

- browse MySQL tables and columns in a tkinter GUI,
- preview the current selection,
- queue one or more import jobs,
- export numeric data into reusable GAMS symbols,
- run `gams/model.gms`,
- produce `data/imported_data.gdx`, listing, log, and generated include files for later GAMS use.

## Project Purpose

The application provides a desktop front-end for workflows where SQL data should be selected interactively and then handed off to GAMS in a consistent, reusable form. It preserves two layers at the same time:

- a backward-compatible primary symbol `data(obs,col)` based on the first queued import job,
- reusable named symbols such as `productsData(obs,col)` or `costData(obs,col)` for later GAMS models.

This is a cross-platform hardening pass of the first stable version. It is not the advanced branch and it does not include semantic redesigns, reconciliation systems, or new architecture from later work.

## Branch And Folder Context

- Active development target for this version: `codex/mysql-to-gams-importer`
- Intended local folder: `C:\Users\Akhan\Desktop\gams-mysql-importer-first`
- Do not mix it with the advanced repository folder `C:\Users\Akhan\Desktop\gams-mysql-importer`

## Architecture Overview

- [app/gui_importer.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/gui_importer.py): tkinter GUI, preview logic, basket management, and user messages
- [app/db.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/db.py): MySQL metadata and preview queries
- [app/exporter.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/exporter.py): export pipeline, generated CSV files, and generated GAMS include files
- [app/models.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/models.py): shared dataclasses
- [app/runner.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/runner.py): GAMS discovery, subprocess launch, and GAMS Studio opening
- [app/utils.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/utils.py): project paths, logging, and configuration loading
- [gams/model.gms](C:/Users/Akhan/Desktop/gams-mysql-importer-first/gams/model.gms): main GAMS entry point
- [scripts/run_app.bat](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/run_app.bat): Windows launcher
- [scripts/run_app.sh](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/run_app.sh): macOS-friendly launcher
- [scripts/setup_windows.ps1](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/setup_windows.ps1): Windows setup
- [scripts/setup_macos.sh](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/setup_macos.sh): macOS setup

High-level flow:

1. Load database settings from `config/db_config.json`, or fall back to `config/db_config.example.json`.
2. Load optional runtime settings from `config/app_config.json`, or fall back to `config/app_config.example.json`.
3. Connect to MySQL and list available tables.
4. List columns for the selected table.
5. Preview the current selection.
6. Queue one or more import jobs.
7. Export one long-format CSV per queued symbol plus compatibility artifacts for the first job.
8. Generate helper GAMS include files for the current basket.
9. Run GAMS on `gams/model.gms`.
10. Attempt to open the model, listing, and GDX artifacts in GAMS Studio when available.

## Folder Structure

```text
gams-mysql-importer-first/
|-- app/
|-- config/
|-- data/
|-- gams/
|-- scripts/
|-- tests/
|-- .gitignore
|-- README.md
`-- requirements.txt
```

Generated at runtime:

- `data/exported_preview.csv`
- `data/exported_data_long.csv`
- `data/import_jobs/<symbol>.csv`
- `data/import_jobs_manifest.csv`
- `data/imported_data.gdx`
- `data/gams_run.lst`
- `data/gams_run.log`
- `gams/generated_import_runtime.gms`
- `gams/generated_import_symbols.gms`
- `gams/generated_unload_symbols.gms`
- `gams/example_use_imported_symbols.gms` may be refreshed for the current basket

## Prerequisites

Applies to both platforms:

- Python 3.11
- access to the target MySQL database
- a MySQL account with permission to read the selected tables
- GAMS installed locally

Platform-specific notes:

- Windows: Python 3.11 via the standard Windows installer or `py -3.11`
- macOS: Python 3.11 from [python.org](https://www.python.org/downloads/macos/) is preferred because it usually includes a working `tkinter` build

## Database Configuration

1. Copy `config/db_config.example.json` to `config/db_config.json`.
2. Replace the placeholder values with your real MySQL settings.
3. Keep `config/db_config.json` local only. It is ignored by git.

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

- `config/db_config.json` is used first when present.
- Otherwise the app falls back to `config/db_config.example.json`.
- The GUI warns when only the example config is available.

## Optional GAMS Runtime Configuration

If GAMS is not on `PATH`, you can create `config/app_config.json` and set explicit paths there.

Start from [config/app_config.example.json](C:/Users/Akhan/Desktop/gams-mysql-importer-first/config/app_config.example.json):

```json
{
  "gams_executable": "",
  "gams_studio_path": ""
}
```

Examples:

- Windows executable path: `C:\\GAMS\\53\\gams.exe`
- macOS executable path: `/Applications/GAMS/53/gams`
- macOS Studio app path: `/Applications/GAMS Studio.app`
- macOS Studio executable path: `/Applications/GAMS Studio.app/Contents/MacOS/GAMS Studio`

Runtime discovery order:

1. `config/app_config.json`
2. `GAMS_EXECUTABLE` / `GAMS_STUDIO_PATH` environment variables
3. `gams` on `PATH`
4. platform-specific fallback discovery

Current fallback discovery:

- Windows: common `C:\GAMS` and `Program Files` layouts
- macOS: common `/Applications` and `~/Applications` GAMS locations when present

## Python Setup On Windows

From PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

This script:

- prefers Python 3.11 via the Windows `py` launcher,
- recreates `.venv` if the existing interpreter is not Python 3.11,
- installs dependencies from `requirements.txt`.

Recommended verification:

```powershell
.\.venv\Scripts\python.exe --version
```

You should see `Python 3.11.x`.

## Python Setup On macOS

From Terminal in the repository root:

```bash
chmod +x scripts/setup_macos.sh scripts/run_app.sh
./scripts/setup_macos.sh
```

This script:

- looks for Python 3.11,
- checks that `tkinter` is available,
- creates `.venv`,
- installs dependencies from `requirements.txt`.

Recommended verification:

```bash
.venv/bin/python --version
.venv/bin/python -c "import tkinter; print('tkinter ok')"
```

If `tkinter` is missing, install Python 3.11 from [python.org](https://www.python.org/downloads/macos/) and rerun the setup script.

## Running The GUI On Windows

After setup:

```powershell
.\.venv\Scripts\python.exe -m app.gui_importer
```

Or launch with:

```text
scripts\run_app.bat
```

## Running The GUI On macOS

After setup:

```bash
.venv/bin/python -m app.gui_importer
```

Or launch with:

```bash
./scripts/run_app.sh
```

## GUI Workflow

1. Click `Connect to Database`.
2. Choose a source table.
3. Select one or more columns.
4. Provide `Output symbol`, `Max rows`, and optional `Filter / WHERE`.
5. Click `Preview Current Selection` when needed.
6. Click `Add Import Job` to queue the current selection.
7. Repeat for more jobs if needed.
8. Review the import basket.
9. Click `Export Basket and Run GAMS`.

Behavior preserved from the first stable version:

- each basket item keeps its own source table, selected columns, row limit, filter, and symbol name,
- the first queued job still becomes `data(obs,col)` for backward compatibility,
- every queued job also produces its own reusable symbol for later GAMS scripts.

## Generated Outputs And Artifacts

Important generated files:

- `data/imported_data.gdx`
- `data/gams_run.lst`
- `data/gams_run.log`
- `gams/generated_import_runtime.gms`
- `gams/generated_import_symbols.gms`
- `gams/generated_unload_symbols.gms`

The application also writes:

- `data/exported_preview.csv`
- `data/exported_data_long.csv`
- `data/import_jobs/<symbol>.csv`
- `data/import_jobs_manifest.csv`

## How GAMS Is Located And Run

When the basket is executed, the application exports the queued jobs and then runs the equivalent of:

```text
gams gams/model.gms
```

The exact executable is located in this order:

1. `config/app_config.json` if `gams_executable` is set
2. `GAMS_EXECUTABLE` if the environment variable is set
3. `gams` from `PATH`
4. platform-specific fallback search

The run writes:

- `data/imported_data.gdx`
- `data/gams_run.lst`
- `data/gams_run.log`

On success, the GUI reports which GAMS executable was used.

## GAMS Studio / Artifact Opening Behavior

Windows behavior is preserved:

- the app tries to open GAMS Studio automatically on the model, listing, and GDX files,
- common Windows Studio layouts are still supported.

macOS behavior:

- if `gams_studio_path` points to a Studio executable or `.app`, that path is used,
- otherwise the app tries `open -a "GAMS Studio"` with the generated files,
- if that fails, the run still succeeds and the GUI tells you to open the artifacts manually.

## Troubleshooting

### GAMS is not found

If the GUI reports that GAMS could not be found:

- confirm `gams` works from a terminal,
- or create `config/app_config.json` and set `gams_executable`,
- or set the `GAMS_EXECUTABLE` environment variable,
- on Windows, verify the local install path such as `C:\GAMS\53\gams.exe`,
- on macOS, verify the executable path and rerun the app from a shell where `PATH` is correct.

### GAMS Studio does not open automatically

- The GAMS run can still succeed even if Studio is not opened.
- Open these files manually if needed:
  - `gams/model.gms`
  - `data/gams_run.lst`
  - `data/imported_data.gdx`
- On macOS, set `gams_studio_path` in `config/app_config.json` if automatic discovery is unreliable.

### `tkinter` is unavailable

- Windows: reinstall Python 3.11 with `tkinter` included.
- macOS: install Python 3.11 from [python.org](https://www.python.org/downloads/macos/) rather than relying on a minimal system or package-manager build.
- Verify with:

```bash
python3.11 -c "import tkinter; print('tkinter ok')"
```

### MySQL connection errors

The GUI provides clearer messages for:

- host name resolution failures,
- access denied errors,
- unreachable MySQL server errors.

Also verify:

- `config/db_config.json` exists,
- placeholder values were replaced,
- the MySQL host, port, user, and password are correct.

## Reusing Imported SQL Data In Your Own GAMS Model

The recommended path is to include:

```gams
$include "gams/generated_import_symbols.gms"
```

That helper declares the current imported symbols and loads them from `data/imported_data.gdx`.

You can also load symbols manually:

```gams
Sets
    obs__productsData(*)
    col__productsData(*);

Parameters
    productsData(obs__productsData<, col__productsData<);

$gdxin data/imported_data.gdx
$load productsData
$gdxin
```

The first queued job is also preserved as:

```gams
data(obs,col)
```

for compatibility with the original first-version workflow and the optional semantic mapping example.

## Testing And Validation

Recommended local checks:

```powershell
python -m compileall app tests
python -m pytest
```

If you want to validate the reusable import pipeline end-to-end:

1. start the GUI,
2. connect to MySQL,
3. queue one or more import jobs,
4. run `Export Basket and Run GAMS`,
5. confirm that `data/imported_data.gdx`, `data/gams_run.lst`, and `data/gams_run.log` exist.

## Remaining Platform Limitations

- Automatic GAMS Studio opening on macOS depends on the local app name, bundle path, or shell environment.
- The GUI uses `tkinter`, so macOS users need a Python build that includes it.
- The importer still exports numeric parameter-style symbols only in the form `<symbolName>(obs,col)`.
- The semantic mapping and demo optimization still operate on the first queued import job through `data(obs,col)`.
- The filter box remains intentionally conservative and is not a full SQL editor.
