"""Subprocess integration for launching a GAMS model."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
from pathlib import Path


class GAMSRunError(RuntimeError):
    """Raised when the GAMS executable cannot be started or returns an error."""


@dataclass
class GAMSRunResult:
    """Artifacts produced by a successful GAMS run."""

    completed_process: subprocess.CompletedProcess[str]
    gams_executable: Path
    model_path: Path
    listing_file: Path
    log_file: Path
    gdx_file: Path
    studio_opened: bool = False
    optimization_solved: bool = False
    optimization_message: str = ""


def find_gams_executable() -> Path | None:
    """Locate the GAMS executable from PATH or common Windows install locations."""
    gams_on_path = shutil.which("gams")
    if gams_on_path:
        return Path(gams_on_path)

    candidate_paths = [
        Path(r"C:\GAMS"),
        Path(r"C:\Program Files\GAMS"),
        Path(r"C:\Program Files (x86)\GAMS"),
    ]
    discovered: list[Path] = []

    for base_path in candidate_paths:
        if not base_path.exists():
            continue
        discovered.extend(base_path.glob("**/gams.exe"))

    if not discovered:
        return None

    return max(discovered, key=lambda path: path.stat().st_mtime)


def find_gams_studio_executable() -> Path | None:
    """Locate GAMS Studio based on common Windows layouts."""
    gams_executable = find_gams_executable()
    candidates: list[Path] = []

    if gams_executable is not None:
        candidates.append(gams_executable.parent / "studio" / "studio.exe")

    candidates.extend(
        [
            Path(r"C:\GAMS\53\studio\studio.exe"),
            Path(r"C:\Program Files\GAMS\studio\studio.exe"),
            Path(r"C:\Program Files (x86)\GAMS\studio\studio.exe"),
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def open_gams_studio(model_path: Path, listing_file: Path, gdx_file: Path) -> bool:
    """Open GAMS Studio on the generated artifacts when available."""
    studio_executable = find_gams_studio_executable()
    if studio_executable is None:
        return False

    subprocess.Popen(
        [
            str(studio_executable),
            str(model_path),
            str(listing_file),
            str(gdx_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
    )
    return True


def summarize_gams_log(log_file: Path) -> tuple[bool, str]:
    """Extract optimization status hints from the GAMS log file."""
    if not log_file.exists():
        return False, ""

    log_text = log_file.read_text(encoding="utf-8", errors="replace")
    if "OPTIMIZATION_SOLVED:" in log_text:
        return True, "Optimization example solved successfully."
    if "OPTIMIZATION_SKIPPED:" in log_text:
        return (
            False,
            "Generic data import succeeded, but the optimization example was skipped because the selected columns did not include a required semantic mapping such as profit and capacity.",
        )
    return False, ""


def run_gams_model(project_root: Path, model_path: Path) -> GAMSRunResult:
    """Run the GAMS model, save standard artifacts, and return their locations."""
    gams_executable = find_gams_executable()
    if gams_executable is None:
        raise GAMSRunError(
            "GAMS executable could not be found. Install GAMS or add it to PATH. "
            "On Windows, a standard installation often looks like C:\\GAMS\\<version>\\gams.exe."
        )

    listing_file = project_root / "data" / "gams_run.lst"
    log_file = project_root / "data" / "gams_run.log"
    gdx_file = project_root / "data" / "imported_data.gdx"

    try:
        completed = subprocess.run(
            [
                str(gams_executable),
                str(model_path),
                f"o={listing_file}",
                f"logFile={log_file}",
                "lo=2",
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PATH": f"{gams_executable.parent}{os.pathsep}{os.environ.get('PATH', '')}"},
        )
    except subprocess.CalledProcessError as exc:
        raise GAMSRunError(
            "GAMS execution failed.\n\n"
            f"Command: {' '.join(exc.cmd)}\n"
            f"Exit code: {exc.returncode}\n"
            f"Stdout:\n{exc.stdout}\n"
            f"Stderr:\n{exc.stderr}"
        ) from exc

    result = GAMSRunResult(
        completed_process=completed,
        gams_executable=gams_executable,
        model_path=model_path,
        listing_file=listing_file,
        log_file=log_file,
        gdx_file=gdx_file,
    )
    result.studio_opened = open_gams_studio(model_path, listing_file, gdx_file)
    result.optimization_solved, result.optimization_message = summarize_gams_log(log_file)
    return result
