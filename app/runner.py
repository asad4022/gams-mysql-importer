"""Subprocess integration for launching a GAMS model."""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import shutil
import subprocess
from pathlib import Path

from .utils import RuntimeConfig


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
    studio_message: str = ""
    optimization_solved: bool = False
    optimization_message: str = ""


GAMS_EXECUTABLE_ENV_VAR = "GAMS_EXECUTABLE"
GAMS_STUDIO_ENV_VAR = "GAMS_STUDIO_PATH"


def _platform_name() -> str:
    return platform.system()


def _configured_path(
    runtime_config: RuntimeConfig | None,
    attribute_name: str,
    env_var_name: str,
) -> tuple[Path | None, str | None]:
    configured_path = getattr(runtime_config, attribute_name, None) if runtime_config else None
    if configured_path is not None:
        return configured_path, f"config/app_config.json:{attribute_name}"

    env_value = os.environ.get(env_var_name, "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve(strict=False), env_var_name

    return None, None


def _validate_configured_executable(path: Path, source: str) -> Path:
    if not path.exists():
        raise GAMSRunError(
            f"GAMS executable configured via {source} was not found: {path}\n\n"
            f"Update {source} or remove it so the application can use 'gams' from PATH instead."
        )
    if path.is_dir():
        raise GAMSRunError(
            f"GAMS executable configured via {source} points to a directory instead of a file: {path}\n\n"
            "Set it to the GAMS executable itself, for example 'gams', 'gams.exe', or the full executable path."
        )
    return path


def _windows_gams_candidates() -> list[Path]:
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

    return discovered


def _macos_gams_candidates() -> list[Path]:
    candidate_paths = [
        Path("/Applications"),
        Path.home() / "Applications",
    ]
    patterns = ("GAMS*/**/gams", "GAMS/**/gams")
    discovered: list[Path] = []

    for base_path in candidate_paths:
        if not base_path.exists():
            continue
        for pattern in patterns:
            discovered.extend(path for path in base_path.glob(pattern) if path.is_file())

    return discovered


def find_gams_executable(runtime_config: RuntimeConfig | None = None) -> Path | None:
    """Locate the GAMS executable from local config, PATH, or common install locations."""
    configured_path, configured_source = _configured_path(
        runtime_config,
        "gams_executable",
        GAMS_EXECUTABLE_ENV_VAR,
    )
    if configured_path is not None and configured_source is not None:
        return _validate_configured_executable(configured_path, configured_source)

    gams_on_path = shutil.which("gams")
    if gams_on_path:
        return Path(gams_on_path)

    platform_name = _platform_name()
    discovered: list[Path] = []
    if platform_name == "Windows":
        discovered = _windows_gams_candidates()
    elif platform_name == "Darwin":
        discovered = _macos_gams_candidates()

    return max(discovered, key=lambda path: path.stat().st_mtime) if discovered else None


def find_gams_studio_executable(
    runtime_config: RuntimeConfig | None = None,
    gams_executable: Path | None = None,
) -> Path | None:
    """Locate GAMS Studio when a direct executable path is available."""
    configured_path, configured_source = _configured_path(
        runtime_config,
        "gams_studio_path",
        GAMS_STUDIO_ENV_VAR,
    )
    if configured_path is not None and configured_source is not None:
        if configured_path.exists() and configured_path.is_file():
            return configured_path
        return None

    if gams_executable is not None:
        platform_name = _platform_name()
        if platform_name == "Windows":
            candidate = gams_executable.parent / "studio" / "studio.exe"
            if candidate.exists():
                return candidate

    studio_on_path = shutil.which("studio")
    if studio_on_path:
        return Path(studio_on_path)

    if _platform_name() == "Windows":
        candidates = [
            Path(r"C:\GAMS\53\studio\studio.exe"),
            Path(r"C:\Program Files\GAMS\studio\studio.exe"),
            Path(r"C:\Program Files (x86)\GAMS\studio\studio.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

    return None


def _open_macos_gams_studio(
    runtime_config: RuntimeConfig | None,
    files_to_open: list[Path],
) -> tuple[bool, str]:
    configured_path, configured_source = _configured_path(
        runtime_config,
        "gams_studio_path",
        GAMS_STUDIO_ENV_VAR,
    )

    try:
        if configured_path is not None and configured_source is not None:
            if configured_path.suffix == ".app" and configured_path.exists():
                subprocess.Popen(
                    ["open", "-a", str(configured_path), *(str(path) for path in files_to_open)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                )
                return True, "GAMS Studio was opened automatically on the model, listing, and GDX data files."
            if configured_path.exists():
                subprocess.Popen(
                    [str(configured_path), *(str(path) for path in files_to_open)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                )
                return True, "GAMS Studio was opened automatically on the model, listing, and GDX data files."
            if not configured_path.exists():
                return (
                    False,
                    f"GAMS completed, but the configured GAMS Studio path was not found: {configured_path}",
                )

        subprocess.Popen(
            ["open", "-a", "GAMS Studio", *(str(path) for path in files_to_open)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
        return True, "GAMS Studio was opened automatically on the model, listing, and GDX data files."
    except OSError:
        return (
            False,
            "GAMS completed, but GAMS Studio could not be opened automatically on macOS. "
            "Open the generated files manually if you want to inspect them.",
        )


def open_gams_studio(
    model_path: Path,
    listing_file: Path,
    gdx_file: Path,
    runtime_config: RuntimeConfig | None = None,
    gams_executable: Path | None = None,
) -> tuple[bool, str]:
    """Open GAMS Studio on the generated artifacts when available."""
    files_to_open = [model_path, listing_file, gdx_file]

    if _platform_name() == "Darwin":
        return _open_macos_gams_studio(runtime_config, files_to_open)

    studio_executable = find_gams_studio_executable(runtime_config, gams_executable)
    if studio_executable is None:
        return (
            False,
            "GAMS completed, but GAMS Studio could not be opened automatically. "
            "Open the model, listing, and GDX files manually if needed.",
        )

    try:
        subprocess.Popen(
            [str(studio_executable), *(str(path) for path in files_to_open)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError:
        return (
            False,
            f"GAMS completed, but GAMS Studio could not be started from {studio_executable}.",
        )
    return True, "GAMS Studio was opened automatically on the model, listing, and GDX data files."


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


def run_gams_model(
    project_root: Path,
    model_path: Path,
    runtime_config: RuntimeConfig | None = None,
) -> GAMSRunResult:
    """Run the GAMS model, save standard artifacts, and return their locations."""
    gams_executable = find_gams_executable(runtime_config)
    if gams_executable is None:
        troubleshooting_lines = [
            "GAMS executable could not be found.",
            "",
            "Set config/app_config.json -> gams_executable,",
            f"or set the {GAMS_EXECUTABLE_ENV_VAR} environment variable,",
            "or make sure 'gams' is available on PATH.",
        ]
        if _platform_name() == "Windows":
            troubleshooting_lines.append(
                "A standard Windows installation often looks like C:\\GAMS\\<version>\\gams.exe."
            )
        raise GAMSRunError(
            "\n".join(troubleshooting_lines)
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
    result.studio_opened, result.studio_message = open_gams_studio(
        model_path,
        listing_file,
        gdx_file,
        runtime_config,
        gams_executable,
    )
    result.optimization_solved, result.optimization_message = summarize_gams_log(log_file)
    return result
