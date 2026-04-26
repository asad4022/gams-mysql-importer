$ErrorActionPreference = "Stop"

# Set up the stable importer with Python 3.11 while preserving the current Windows workflow.
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"

function Get-PreferredPython {
    try {
        $pyLauncher = Get-Command py -ErrorAction Stop
        if ($pyLauncher) {
            return @("py", "-3.11")
        }
    }
    catch {
    }

    return @("python")
}

$pythonCommand = Get-PreferredPython
$pythonArgsForVersion = $pythonCommand + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
$selectedPythonVersion = (& $pythonArgsForVersion[0] $pythonArgsForVersion[1..($pythonArgsForVersion.Length - 1)]) 2>$null

if (-not $selectedPythonVersion) {
    throw "Python 3.11 was not found. Install Python 3.11 and re-run this script."
}

if ($selectedPythonVersion.Trim() -ne "3.11") {
    throw "This project requires Python 3.11. Detected Python $selectedPythonVersion."
}

$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (Test-Path $pythonExe) {
    $existingVersion = & $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($existingVersion.Trim() -ne "3.11") {
        Write-Host "Existing virtual environment uses Python $existingVersion. Recreating with Python 3.11..."
        Remove-Item -LiteralPath $venvPath -Recurse -Force
    }
}

if (-not (Test-Path $venvPath)) {
    & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Length - 1)] -m venv $venvPath
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $projectRoot "requirements.txt")

$gamsCommand = Get-Command gams -ErrorAction SilentlyContinue
if ($gamsCommand) {
    Write-Host "Detected GAMS on PATH: $($gamsCommand.Source)"
}
else {
    Write-Host "GAMS was not found on PATH."
    Write-Host "If GAMS is installed, copy config\\app_config.example.json to config\\app_config.json and set gams_executable."
}

Write-Host ""
Write-Host "Environment setup complete."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Verify tkinter with: .\.venv\Scripts\python.exe -c `"import tkinter; print('tkinter ok')`""
Write-Host "Verify GAMS with: Get-Command gams"
Write-Host "Run with: .\.venv\Scripts\python.exe -m app.gui_importer"
