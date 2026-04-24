"""Checks for packaged resource layout and model checkpoint references."""

from __future__ import annotations

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


def test_user_facing_models_register_thirty_day_checkpoints() -> None:
    registry = load_models_registry()
    models = {
        model.get("id"): model
        for model in registry.get("models", [])
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    }

    expected = {
        "dc_itransformer_ampds": "resources/checkpoints/dc_itransformer_ampds_30d.pth",
        "dc_itransformer_londonb0": "resources/checkpoints/dc_itransformer_londonb0_30d.pth",
        "patchtst_ampds": "resources/checkpoints/patchtst_ampds_30d.pth",
        "patchtst_londonb0": "resources/checkpoints/patchtst_londonb0_30d.pth",
        "timexer_ampds": "resources/checkpoints/timexer_ampds_30d.pth",
        "timexer_londonb0": "resources/checkpoints/timexer_londonb0_30d.pth",
    }

    for model_id, checkpoint in expected.items():
        horizons = models[model_id]["horizons"]
        assert horizons["30d"]["pred_len_hours"] == 720
        assert horizons["30d"]["checkpoint"] == checkpoint
