"""High-level forecast API: horizon mapping, registry resolution, runner."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Optional, Union

import numpy as np
import pandas as pd

from inference_engine.model_registry import resolve_model_bundle
from inference_engine.runner import ForecastOutput, ForecastRunner

ValueSequence = Union[Sequence[float], np.ndarray, pd.Series]


class ForecastUnavailableError(RuntimeError):
    """Raised when the model bundle is not ready (checkpoint, horizon, etc.)."""


_SUPPORTED_HORIZON_STEPS: dict[str, int] = {
    "1d": 24,
    "7d": 168,
    "30d": 720,
}


def horizon_to_steps(horizon: str) -> int:
    """
    Map a horizon key to hourly step count (与 models.json 中 pred_len_hours 对齐).

    Raises
    ------
    TypeError
        If *horizon* is not a string.
    ValueError
        If *horizon* is empty or not a supported key.
    """
    if not isinstance(horizon, str):
        raise TypeError("horizon 必须是字符串，例如 1d 或 7d。")
    key = horizon.strip().lower()
    if not key:
        raise ValueError("horizon 不能为空。")
    if key not in _SUPPORTED_HORIZON_STEPS:
        supported = "、".join(sorted(_SUPPORTED_HORIZON_STEPS.keys()))
        raise ValueError(f"不支持的预测周期「{key}」。支持的周期：{supported}。")
    return _SUPPORTED_HORIZON_STEPS[key]


class ForecastService:
    """Orchestrates ``resolve_model_bundle`` + :class:`ForecastRunner`."""

    def run_forecast(
        self,
        model_name: str,
        horizon: str,
        values: ValueSequence,
        *,
        registry: Optional[dict[str, Any]] = None,
    ) -> ForecastOutput:
        """
        Resolve model + horizon, then run the shared :class:`ForecastRunner`.

        步数优先使用注册表 ``pred_len_hours``（若为正整数），否则回退到
        :func:`horizon_to_steps`。
        """
        bundle = resolve_model_bundle(model_name, horizon, registry=registry)
        if not bundle["is_available"]:
            raise ForecastUnavailableError(bundle.get("message") or "预测不可用。")

        reg_steps = bundle.get("pred_len_hours")
        if type(reg_steps) is int and reg_steps > 0:
            steps = reg_steps
        else:
            steps = horizon_to_steps(horizon)

        runner = ForecastRunner(
            model_id=bundle["model_name"],
            checkpoint_path=bundle["checkpoint_path"],
        )
        return runner.run(values, steps)
