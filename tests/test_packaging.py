"""Checks for packaged resource layout and model checkpoint references."""

from __future__ import annotations

from pathlib import Path

from app.config import load_models_registry
from app.paths import PROJECT_ROOT


def test_build_ps1_exists() -> None:
    assert (PROJECT_ROOT / "build.ps1").is_file()


def test_pyinstaller_spec_exists() -> None:
    spec = PROJECT_ROOT / "pyinstaller.spec"
    assert spec.is_file()
    text = spec.read_text(encoding="utf-8")
    assert "main.py" in text
    assert "resources" in text


def test_models_registry_uses_project_relative_checkpoint_paths() -> None:
    registry = load_models_registry()
    checkpoints: list[str] = []
    for model in registry.get("models", []):
        horizons = model.get("horizons", {})
        if not isinstance(horizons, dict):
            continue
        for spec in horizons.values():
            if isinstance(spec, dict) and isinstance(spec.get("checkpoint"), str):
                checkpoints.append(spec["checkpoint"])

    assert checkpoints, "至少应有一组模型 checkpoint 被登记用于打包。"
    for checkpoint in checkpoints:
        normalized = checkpoint.replace("\\", "/")
        assert not normalized.startswith("D:/"), checkpoint
        assert normalized.startswith("resources/checkpoints/"), checkpoint


def test_registered_checkpoint_files_exist_under_resources() -> None:
    registry = load_models_registry()
    for model in registry.get("models", []):
        horizons = model.get("horizons", {})
        if not isinstance(horizons, dict):
            continue
        for horizon_spec in horizons.values():
            checkpoint = horizon_spec.get("checkpoint") if isinstance(horizon_spec, dict) else None
            if not isinstance(checkpoint, str):
                continue
            path = PROJECT_ROOT / checkpoint
            assert path.is_file(), f"缺少 checkpoint 文件：{path}"
