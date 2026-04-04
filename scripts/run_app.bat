@echo off
setlocal
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.gui_importer
) else (
    python -m app.gui_importer
)

endlocal
