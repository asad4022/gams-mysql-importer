# MySQL to GAMS Importer

This repository is the first stable version of the MySQL-to-GAMS desktop importer. The intended working copy for this version is:

- folder: `C:\Users\Akhan\Desktop\gams-mysql-importer-first`
- stable branch: `codex/mysql-to-gams-importer`

This version is the recommended starting point for first-time users. It preserves the original stable workflow while making setup and launch clearer on both Windows and macOS.

The application lets a user:

- connect to a MySQL database,
- browse tables and columns in a tkinter GUI,
- preview the current selection,
- queue one or more import jobs,
- export numeric columns into reusable GAMS symbols,
- run `gams/model.gms`,
- inspect `data/imported_data.gdx`, the GAMS log, the listing file, and generated helper files.

## Recommended Branch For First-Time Users

Use the stable branch first:

- `codex/mysql-to-gams-importer`: stable cross-platform importer for day-to-day use
- `feature/next-gen-import-workflow`: advanced research branch with newer ideas and experiments

If you are new to this project, start with `codex/mysql-to-gams-importer`.

## What This Stable Version Does

The stable importer keeps the current architecture and workflow:

- the first queued import job is still exposed as the backward-compatible primary symbol `data(obs,col)`,
- each queued import job also creates its own reusable symbol such as `productsData(obs,col)` or `costData(obs,col)`,
- the app still runs `gams/model.gms`,
- the app still writes `data/imported_data.gdx` for later GAMS use.

This repository is not the advanced branch and does not include next-generation reconciliation or semantic redesign features.

## Project Structure

- [app/gui_importer.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/gui_importer.py): GUI, basket management, preview workflow, and user messages
- [app/db.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/db.py): MySQL metadata and preview queries
- [app/exporter.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/exporter.py): export pipeline and generated GAMS helper files
- [app/models.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/models.py): shared dataclasses
- [app/runner.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/runner.py): GAMS discovery, execution, and GAMS Studio opening
- [app/utils.py](C:/Users/Akhan/Desktop/gams-mysql-importer-first/app/utils.py): logging and configuration loading
- [gams/model.gms](C:/Users/Akhan/Desktop/gams-mysql-importer-first/gams/model.gms): main GAMS entry point
- [scripts/setup_windows.ps1](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/setup_windows.ps1): Windows setup helper
- [scripts/setup_macos.sh](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/setup_macos.sh): macOS setup helper
- [scripts/run_app.bat](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/run_app.bat): Windows launcher
- [scripts/run_app.sh](C:/Users/Akhan/Desktop/gams-mysql-importer-first/scripts/run_app.sh): macOS launcher

## Prerequisites

For both platforms:

- Python 3.11
- GAMS installed locally
- access to a MySQL server
- a MySQL user account with permission to read the relevant tables

Helpful platform notes:

- macOS: Python 3.11 from [python.org](https://www.python.org/downloads/macos/) is strongly recommended because it usually includes a working `tkinter` build
- Windows: Python 3.11 from python.org or the Windows `py` launcher is fine
- If you already have MySQL Workbench on macOS, it is useful for confirming your host, port, database name, and table names before using the importer, but the app does not require Workbench itself

## Windows Quick Start

From PowerShell:

```powershell
git clone <repo-url> gams-mysql-importer-first
cd .\gams-mysql-importer-first
git checkout codex/mysql-to-gams-importer
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
Copy-Item .\config\db_config.example.json .\config\db_config.json
.\.venv\Scripts\python.exe -c "import tkinter; print('tkinter ok')"
Get-Command gams
.\.venv\Scripts\python.exe -m app.gui_importer
```

If GAMS is not on `PATH`, also create a runtime config:

```powershell
Copy-Item .\config\app_config.example.json .\config\app_config.json
```

Then edit `config/app_config.json` and set `gams_executable` and, if needed, `gams_studio_path`.

## macOS Quick Start

From Terminal:

```bash
git clone <repo-url> gams-mysql-importer-first
cd gams-mysql-importer-first
git checkout codex/mysql-to-gams-importer
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
chmod +x scripts/setup_macos.sh scripts/run_app.sh
./scripts/setup_macos.sh
cp config/db_config.example.json config/db_config.json
python -c "import tkinter; print('tkinter ok')"
command -v gams
./scripts/run_app.sh
```

If `gams` is not on `PATH`, also create a runtime config:

```bash
cp config/app_config.example.json config/app_config.json
```

Then edit `config/app_config.json` and set `gams_executable` and, if needed, `gams_studio_path`.

## macOS First-Time Onboarding

This is the recommended path for a first-time macOS user who already has GAMS, MySQL, and MySQL Workbench installed.

1. Clone the repository and check out `codex/mysql-to-gams-importer`.
2. Create and activate a Python 3.11 virtual environment.
3. Install dependencies from `requirements.txt`.
4. Run `./scripts/setup_macos.sh` to verify Python 3.11, verify `tkinter`, and finalize the local environment.
5. Copy `config/db_config.example.json` to `config/db_config.json`.
6. Open `config/db_config.json` and fill in the real MySQL host, port, database, username, and password.
7. If helpful, use MySQL Workbench to confirm that those values are correct and that the target tables exist.
8. Confirm `tkinter` manually:

```bash
python -c "import tkinter; print('tkinter ok')"
```

9. Confirm GAMS discovery:

```bash
command -v gams
```

10. If that command returns nothing, create `config/app_config.json` from the example file and set the full path to the GAMS executable.
11. Launch the GUI:

```bash
./scripts/run_app.sh
```

12. In the GUI:
    connect to the database, choose a table, choose one or more columns, and click `Preview Current Selection`
13. Add the selection to the basket and click `Export Basket and Run GAMS`
14. After the run completes, inspect `data/imported_data.gdx` first
15. If you need more detail, inspect `data/gams_run.log` next and `data/gams_run.lst` after that

## Exact Setup Flow For This Stable Version

The stable setup flow is:

1. clone the repository
2. check out `codex/mysql-to-gams-importer`
3. create a Python 3.11 virtual environment
4. install requirements
5. copy `config/db_config.example.json` to `config/db_config.json`
6. optionally copy `config/app_config.example.json` to `config/app_config.json`
7. verify `tkinter`
8. verify GAMS discovery
9. launch the GUI
10. preview a table
11. export and run GAMS
12. inspect the generated run artifacts

## Configuration Files

### Database Configuration

Copy:

- `config/db_config.example.json` -> `config/db_config.json`

Example content:

```json
{
  "host": "160.78.47.10",
  "port": 3306,
  "database": "RICA",
  "user": "usergams",
  "password": "your-real-password"
}
```

Behavior:

- the app uses `config/db_config.json` first when present
- otherwise it falls back to `config/db_config.example.json`
- the GUI warns if the example config is being used

### Optional Runtime Configuration For GAMS

Copy when needed:

- `config/app_config.example.json` -> `config/app_config.json`

Example content:

```json
{
  "gams_executable": "",
  "gams_studio_path": ""
}
```

Typical values:

- Windows `gams_executable`: `C:\\GAMS\\53\\gams.exe`
- macOS `gams_executable`: `/Applications/GAMS/53/gams`
- macOS `gams_studio_path`: `/Applications/GAMS Studio.app`
- macOS Studio executable path: `/Applications/GAMS Studio.app/Contents/MacOS/GAMS Studio`

Discovery order:

1. `config/app_config.json`
2. `GAMS_EXECUTABLE` and `GAMS_STUDIO_PATH`
3. `gams` from `PATH`
4. platform-specific fallback discovery

## Running The GUI

Windows:

```powershell
.\.venv\Scripts\python.exe -m app.gui_importer
```

Or:

```text
scripts\run_app.bat
```

macOS:

```bash
.venv/bin/python -m app.gui_importer
```

Or:

```bash
./scripts/run_app.sh
```

## GUI Workflow

1. Click `Connect to Database`.
2. Choose a source table.
3. Select one or more columns.
4. Enter `Output symbol`, `Max rows`, and an optional `Filter / WHERE`.
5. Click `Preview Current Selection`.
6. Click `Add Import Job`.
7. Repeat if you want additional symbols.
8. Review the basket.
9. Click `Export Basket and Run GAMS`.

Stable behavior that is preserved:

- the first queued job still becomes `data(obs,col)`
- each queued job also produces its own reusable symbol
- the stable exporter still writes compatibility files for the first queued job

## What A Successful Run Produces

After a successful run, the most important files are:

- `data/imported_data.gdx`
- `data/gams_run.log`
- `data/gams_run.lst`
- `gams/generated_import_runtime.gms`
- `gams/generated_import_symbols.gms`
- `gams/generated_unload_symbols.gms`

Other generated outputs:

- `data/exported_preview.csv`
- `data/exported_data_long.csv`
- `data/import_jobs_manifest.csv`
- `data/import_jobs/<symbol>.csv`

For a first-time user, inspect these in this order:

1. `data/imported_data.gdx`
2. `data/gams_run.log`
3. `data/gams_run.lst`
4. `gams/generated_import_symbols.gms`

Why these files matter:

- `data/imported_data.gdx`: the main imported GAMS data artifact for this run
- `data/gams_run.log`: the fastest text summary of what happened during the GAMS run
- `data/gams_run.lst`: deeper GAMS execution detail
- `gams/generated_import_symbols.gms`: the helper include to reuse imported symbols from another GAMS model

## Inspecting The Result In GAMS Studio

If GAMS Studio opens automatically, inspect `data/imported_data.gdx` first.

If it does not open automatically:

- open `data/imported_data.gdx` manually in GAMS Studio
- then open `data/gams_run.log`
- then open `data/gams_run.lst` if you need deeper diagnostics

## How GAMS Is Located

When the app runs GAMS, it looks in this order:

1. `config/app_config.json`
2. `GAMS_EXECUTABLE`
3. `gams` on `PATH`
4. platform-specific fallback discovery

If GAMS is found, the GUI reports which executable was used.

## Troubleshooting

### `tkinter` is unavailable

Windows:

- reinstall Python 3.11 with `tkinter` included
- verify with:

```powershell
.\.venv\Scripts\python.exe -c "import tkinter; print('tkinter ok')"
```

macOS:

- install Python 3.11 from [python.org](https://www.python.org/downloads/macos/)
- recreate the virtual environment
- rerun `./scripts/setup_macos.sh`
- verify with:

```bash
python -c "import tkinter; print('tkinter ok')"
```

### GAMS is not found

If the GUI reports that GAMS could not be found:

- confirm the command works in a shell:

```bash
command -v gams
```

- or on Windows:

```powershell
Get-Command gams
```

- if GAMS is not on `PATH`, create `config/app_config.json`
- set `gams_executable` to the full executable path
- if needed, also set `gams_studio_path`

Common examples:

- Windows: `C:\GAMS\53\gams.exe`
- macOS: `/Applications/GAMS/53/gams`

### `config/db_config.json` is missing or incorrect

If `config/db_config.json` is missing:

- copy it from `config/db_config.example.json`

If it exists but the app still fails:

- verify that `host`, `port`, `database`, `user`, and `password` were updated from placeholder values
- verify the database is reachable from the local machine
- verify the selected user can read the target tables
- if you have MySQL Workbench, use it to confirm the same connection details outside the importer

The GUI already provides clearer messages for:

- host name resolution failures
- access denied errors
- unreachable MySQL server errors

### GAMS Studio does not open automatically

- the import and GAMS run may still have succeeded
- open `data/imported_data.gdx` manually first
- on macOS, set `gams_studio_path` in `config/app_config.json` if automatic discovery is unreliable

## Reusing Imported SQL Data In Your Own GAMS Model

The recommended helper is:

```gams
$include "gams/generated_import_symbols.gms"
```

That file declares the current imported symbols and loads them from `data/imported_data.gdx`.

The first queued job is still preserved as:

```gams
data(obs,col)
```

for compatibility with the original stable workflow.

## Validation

Recommended low-risk checks:

```powershell
python -m compileall app tests
python -m pytest
```

Practical runtime validation:

1. launch the GUI
2. connect to MySQL
3. preview a real table
4. export and run GAMS
5. confirm that `data/imported_data.gdx`, `data/gams_run.log`, and `data/gams_run.lst` exist

## Remaining Platform Limitations

- Automatic GAMS Studio opening on macOS still depends on the local Studio app name, bundle path, or shell environment.
- macOS still requires a Python build with `tkinter`.
- The importer still exports numeric parameter-style symbols in the stable form `<symbolName>(obs,col)`.
- The first queued import job remains the backward-compatible primary symbol `data(obs,col)`.
- The filter box remains intentionally conservative and is not a full SQL editor.
