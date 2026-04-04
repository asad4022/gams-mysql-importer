"""Subprocess integration for launching a GAMS model."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class GAMSRunError(RuntimeError):
    """Raised when the GAMS executable cannot be started or returns an error."""


def run_gams_model(project_root: Path, model_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the GAMS model and return the completed process."""
    gams_executable = shutil.which("gams")
    if gams_executable is None:
        raise GAMSRunError(
            "GAMS executable not found on PATH. Install GAMS and ensure the "
            "'gams' command is available from a terminal."
        )

    try:
        completed = subprocess.run(
            [gams_executable, str(model_path)],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GAMSRunError(
            "GAMS execution failed.\n\n"
            f"Command: {' '.join(exc.cmd)}\n"
            f"Exit code: {exc.returncode}\n"
            f"Stdout:\n{exc.stdout}\n"
            f"Stderr:\n{exc.stderr}"
        ) from exc

    return completed
