"""Unit tests for runtime configuration and GAMS executable discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.runner import GAMSRunError, find_gams_executable
from app.utils import RuntimeConfig, load_runtime_config


def test_load_runtime_config_resolves_relative_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    app_config = config_dir / "app_config.json"
    app_config.write_text(
        '{\n  "gams_executable": "tools/gams/bin/gams",\n  "gams_studio_path": "Applications/GAMS Studio.app"\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("app.utils.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("app.utils.CONFIG_DIR", config_dir)

    runtime_config, warnings = load_runtime_config()

    assert warnings == []
    assert runtime_config.gams_executable == (tmp_path / "tools/gams/bin/gams").resolve(strict=False)
    assert runtime_config.gams_studio_path == (tmp_path / "Applications/GAMS Studio.app").resolve(strict=False)


def test_find_gams_executable_prefers_configured_path(tmp_path: Path) -> None:
    configured_gams = tmp_path / "gams" / "gams"
    configured_gams.parent.mkdir(parents=True)
    configured_gams.write_text("", encoding="utf-8")

    result = find_gams_executable(RuntimeConfig(gams_executable=configured_gams))

    assert result == configured_gams


def test_find_gams_executable_raises_for_missing_configured_path(tmp_path: Path) -> None:
    missing_gams = tmp_path / "missing" / "gams"

    with pytest.raises(GAMSRunError, match="config/app_config.json:gams_executable"):
        find_gams_executable(RuntimeConfig(gams_executable=missing_gams))


def test_find_gams_executable_falls_back_to_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    gams_on_path = tmp_path / "bin" / "gams"
    gams_on_path.parent.mkdir(parents=True)
    gams_on_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("app.runner.shutil.which", lambda name: str(gams_on_path) if name == "gams" else None)

    result = find_gams_executable(RuntimeConfig())

    assert result == gams_on_path
