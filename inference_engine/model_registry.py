"""Resolve model id + horizon to checkpoint path with availability gating."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.config import load_models_registry
from app.paths import PROJECT_ROOT

_CONFIG_METADATA_KEYS = (
    "label",
    "seq_len",
    "label_len",
    "features_mode",
    "enc_in",
    "target_column",
    "required_columns",
    "dataset_line",
)


def _attach_entry_metadata(base: dict[str, Any], entry: dict[str, Any]) -> None:
    for key in _CONFIG_METADATA_KEYS:
        if key in entry:
            base[key] = entry[key]


def _normalize_model_id(model_name: str) -> str:
    return model_name.strip().lower()


def _normalize_horizon(horizon: Any) -> Optional[str]:
    if not isinstance(horizon, str):
        return None
    return horizon.strip().lower()


def _checkpoint_path_from_config(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    if not isinstance(raw, str):
        return None
    path = Path(raw.strip())
    if path.is_absolute():
        return str(path.resolve())
    return str((PROJECT_ROOT / path).resolve())


def resolve_model_bundle(
    model_name: str,
    horizon: Any,
    *,
    registry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Resolve registry entry for (model_name, horizon).

    model_name matches JSON ``id`` (case-insensitive).
    horizon matches keys under ``horizons`` (e.g. ``1d``, ``7d``).
    """
    reg = registry if registry is not None else load_models_registry()
    models = reg.get("models") or []
    want_id = _normalize_model_id(model_name)
    h = _normalize_horizon(horizon)

    entry: Optional[dict[str, Any]] = None
    for m in models:
        mid = m.get("id")
        if isinstance(mid, str) and _normalize_model_id(mid) == want_id:
            entry = m
            break

    base: dict[str, Any] = {
        "is_available": False,
        "model_name": model_name.strip(),
        "horizon": h,
        "pred_len_hours": None,
        "checkpoint_path": None,
        "message": "",
    }

    if h is None:
        base["message"] = "horizon 必须是字符串，例如 1d 或 7d。"
        return base

    if entry is None:
        base["message"] = f"未注册的模型：{model_name.strip()}。"
        return base

    _attach_entry_metadata(base, entry)

    horizons = entry.get("horizons") or {}
    if not isinstance(horizons, dict):
        base["message"] = "模型配置异常：horizons 无效。"
        return base

    normalized_horizons = {
        key.strip().lower(): value for key, value in horizons.items() if isinstance(key, str)
    }

    if h not in normalized_horizons:
        supported = sorted(normalized_horizons.keys())
        joined = "、".join(supported) if supported else "无"
        base["message"] = (
            f"该模型不支持预测周期「{h}」。支持的周期：{joined}。"
        )
        return base

    spec = normalized_horizons[h]
    if not isinstance(spec, dict):
        base["message"] = "模型配置异常：该周期条目无效。"
        return base

    pred_len_hours = spec.get("pred_len_hours")
    base["pred_len_hours"] = pred_len_hours

    raw_ckpt = spec.get("checkpoint")
    resolved = _checkpoint_path_from_config(raw_ckpt)
    if resolved is None:
        base["message"] = "模型资源尚未准备完成，请稍后再试或联系管理员。"
        return base

    base["checkpoint_path"] = resolved
    if not Path(resolved).is_file():
        base["message"] = "模型资源尚未准备完成：checkpoint 文件不存在或路径不是文件。"
        return base

    base["is_available"] = True
    base["message"] = "模型与检查点就绪。"
    return base
