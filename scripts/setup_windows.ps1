$ErrorActionPreference = "Stop"

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

Write-Host ""
Write-Host "Environment setup complete."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run with: .\.venv\Scripts\python.exe -m app.gui_importer"
