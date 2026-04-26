@echo off
setlocal

rem Launch the stable GUI from the repository root.
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.gui_importer
) else (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        "%LocalAppData%\Programs\Python\Python311\python.exe" -m app.gui_importer
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo Python was not found.
            echo Run scripts\setup_windows.ps1 first, or install Python 3.11 before launching the app.
            exit /b 1
        )
        python -m app.gui_importer
    )
)

endlocal
