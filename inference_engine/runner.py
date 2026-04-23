"""
Shared forecast runner: stub baseline + selected real-model runtime paths.

Public API: ``ForecastRunner.run(values, horizon_steps) -> ForecastOutput``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import pandas as pd

ValueSequence = Union[Sequence[float], np.ndarray, pd.Series]


@dataclass(frozen=True)
class ForecastOutput:
    """Result of a single forecast call."""

    history: np.ndarray
    """Observed input window, shape ``(n,)``, float64."""

    prediction: np.ndarray
    """Forecast horizon, shape ``(horizon_steps,)``, float64."""


def _normalize_model_id(model_id: Optional[str]) -> str:
    return (model_id or "").strip().lower()


def _extract_datetime_index_window(
    values: ValueSequence,
    *,
    seq_len: int,
) -> pd.DatetimeIndex | None:
    if not isinstance(values, pd.Series):
        return None
    if not isinstance(values.index, pd.DatetimeIndex):
        return None
    if len(values.index) < seq_len:
        return None
    return values.index[-seq_len:]


class ForecastRunner:
    """
    Entry point for household load forecasting.

    When ``model_id`` maps to a supported runtime model and ``checkpoint_path`` points to a
    valid checkpoint, runs a strict-loaded PyTorch forward pass. Otherwise uses a last-value
    persistence stub (for early integration / tests).
    """

    def __init__(
        self,
        *,
        model_id: Optional[str] = None,
        checkpoint_path: Optional[Union[str, Path]] = None,
        device: Optional[str] = None,
    ) -> None:
        self._model_id = model_id
        self._checkpoint_path = (
            Path(checkpoint_path).resolve() if checkpoint_path is not None else None
        )
        self._device = device
        self._dc_model: Any = None
        self._dc_cfg: Any = None
        self._patchtst_model: Any = None
        self._patchtst_cfg: Any = None
        self._timexer_model: Any = None
        self._timexer_cfg: Any = None

    def _use_dc_londonb0_real(self) -> bool:
        if _normalize_model_id(self._model_id) not in {
            "dc_itransformer_londonb0",
            "dc_itransformer_ampds",
        }:
            return False
        if self._checkpoint_path is None or not self._checkpoint_path.is_file():
            return False
        return True

    def _use_patchtst_real(self) -> bool:
        if _normalize_model_id(self._model_id) not in {"patchtst_ampds", "patchtst_londonb0"}:
            return False
        if self._checkpoint_path is None or not self._checkpoint_path.is_file():
            return False
        return True

    def _use_timexer_real(self) -> bool:
        if _normalize_model_id(self._model_id) not in {"timexer_ampds", "timexer_londonb0"}:
            return False
        if self._checkpoint_path is None or not self._checkpoint_path.is_file():
            return False
        return True

    def _ensure_dc_loaded(self) -> None:
        if self._dc_model is not None:
            return
        from inference_engine.dc_runtime_model import load_dc_itransformer_checkpoint

        assert self._checkpoint_path is not None
        device = self._device or "cpu"
        model, cfg = load_dc_itransformer_checkpoint(self._checkpoint_path, map_location=device)
        self._dc_model = model
        self._dc_cfg = cfg

    def _ensure_patchtst_loaded(self) -> None:
        if self._patchtst_model is not None:
            return
        from inference_engine.patchtst_runtime_model import load_patchtst_checkpoint

        assert self._checkpoint_path is not None
        device = self._device or "cpu"
        model, cfg = load_patchtst_checkpoint(self._checkpoint_path, map_location=device)
        self._patchtst_model = model
        self._patchtst_cfg = cfg

    def _ensure_timexer_loaded(self) -> None:
        if self._timexer_model is not None:
            return
        from inference_engine.timexer_runtime_model import load_timexer_checkpoint

        assert self._checkpoint_path is not None
        device = self._device or "cpu"
        model, cfg = load_timexer_checkpoint(self._checkpoint_path, map_location=device)
        self._timexer_model = model
        self._timexer_cfg = cfg

    def _run_dc_londonb0(
        self,
        values: ValueSequence,
        hist: np.ndarray,
        horizon_steps: int,
    ) -> ForecastOutput:
        import torch

        from inference_engine.time_features_hourly import time_features_hourly

        self._ensure_dc_loaded()
        cfg = self._dc_cfg
        model = self._dc_model
        seq_len = cfg.seq_len
        pred_len = cfg.pred_len

        if hist.size < seq_len:
            raise ValueError(
                f"历史序列长度不足：至少需要 {seq_len} 个点（当前 {hist.size} 个）。"
            )
        if horizon_steps != pred_len:
            raise ValueError(
                f"预测步数必须与模型训练一致：需要 {pred_len}，当前为 {horizon_steps}。"
            )

        window = hist[-seq_len:].astype(np.float32, copy=False)
        x_enc = torch.from_numpy(window).view(1, seq_len, 1)
        time_index = _extract_datetime_index_window(values, seq_len=seq_len)
        x_mark = torch.from_numpy(
            time_features_hourly(seq_len, index=time_index)
        ).view(1, seq_len, 4)

        device = next(model.parameters()).device
        x_enc = x_enc.to(device)
        x_mark = x_mark.to(device)

        label_len = 48
        x_dec = torch.zeros(1, label_len + pred_len, 1, device=device, dtype=x_enc.dtype)
        x_mark_dec = torch.zeros(1, label_len + pred_len, 4, device=device, dtype=x_mark.dtype)

        with torch.no_grad():
            out = model(x_enc, x_mark, x_dec, x_mark_dec)

        pred = out[0, :, 0].detach().cpu().numpy().astype(np.float64)
        return ForecastOutput(history=hist.copy(), prediction=pred)

    def _run_patchtst(
        self,
        hist: np.ndarray,
        horizon_steps: int,
    ) -> ForecastOutput:
        import torch

        self._ensure_patchtst_loaded()
        cfg = self._patchtst_cfg
        model = self._patchtst_model
        seq_len = cfg.seq_len
        pred_len = cfg.pred_len

        if hist.size < seq_len:
            raise ValueError(
                f"历史序列长度不足：PatchTST 至少需要 {seq_len} 个点（当前 {hist.size} 个）。"
            )
        if horizon_steps != pred_len:
            raise ValueError(
                f"预测步数必须与 PatchTST checkpoint 一致：需要 {pred_len}，当前为 {horizon_steps}。"
            )

        window = hist[-seq_len:].astype(np.float32, copy=False)
        x_enc = torch.from_numpy(window).view(1, seq_len, 1)
        x_dec = torch.zeros(1, cfg.label_len + pred_len, 1, dtype=x_enc.dtype)

        device = next(model.parameters()).device
        x_enc = x_enc.to(device)
        x_dec = x_dec.to(device)

        with torch.no_grad():
            out = model(x_enc, None, x_dec, None)

        pred = out[0, :, 0].detach().cpu().numpy().astype(np.float64)
        return ForecastOutput(history=hist.copy(), prediction=pred)

    def _run_timexer(
        self,
        values: ValueSequence,
        hist: np.ndarray,
        horizon_steps: int,
    ) -> ForecastOutput:
        import torch

        from inference_engine.time_features_hourly import time_features_hourly

        self._ensure_timexer_loaded()
        cfg = self._timexer_cfg
        model = self._timexer_model
        seq_len = cfg.seq_len
        pred_len = cfg.pred_len

        if hist.size < seq_len:
            raise ValueError(
                f"历史序列长度不足：TimeXer 至少需要 {seq_len} 个点（当前 {hist.size} 个）。"
            )
        if horizon_steps != pred_len:
            raise ValueError(
                f"预测步数必须与 TimeXer checkpoint 一致：需要 {pred_len}，当前为 {horizon_steps}。"
            )

        window = hist[-seq_len:].astype(np.float32, copy=False)
        x_enc = torch.from_numpy(window).view(1, seq_len, 1)
        time_index = _extract_datetime_index_window(values, seq_len=seq_len)
        x_mark = torch.from_numpy(
            time_features_hourly(seq_len, index=time_index)
        ).view(1, seq_len, 4)

        device = next(model.parameters()).device
        x_enc = x_enc.to(device)
        x_mark = x_mark.to(device)

        x_dec = torch.zeros(1, cfg.label_len + pred_len, 1, device=device, dtype=x_enc.dtype)
        x_mark_dec = torch.zeros(1, cfg.label_len + pred_len, 4, device=device, dtype=x_mark.dtype)

        with torch.no_grad():
            out = model(x_enc, x_mark, x_dec, x_mark_dec)

        pred = out[0, :, 0].detach().cpu().numpy().astype(np.float64)
        return ForecastOutput(history=hist.copy(), prediction=pred)

    def run(self, values: ValueSequence, horizon_steps: int) -> ForecastOutput:
        """
        Run a forecast for ``horizon_steps`` steps ahead.

        Parameters
        ----------
        values :
            Historical scalar series (e.g. kW); non-empty.
        horizon_steps :
            Number of future steps to predict; must be >= 1.

        Returns
        -------
        ForecastOutput
            Copies of ``history`` and the forecast vector ``prediction``.
        """
        if horizon_steps < 1:
            raise ValueError("horizon_steps must be >= 1")

        hist = np.asarray(values, dtype=np.float64).reshape(-1)
        if hist.size < 1:
            raise ValueError("values must be non-empty")

        if self._use_dc_londonb0_real():
            return self._run_dc_londonb0(values, hist, horizon_steps)
        if self._use_patchtst_real():
            return self._run_patchtst(hist, horizon_steps)
        if self._use_timexer_real():
            return self._run_timexer(values, hist, horizon_steps)

        last = float(hist[-1])
        prediction = np.full(horizon_steps, last, dtype=np.float64)

        return ForecastOutput(history=hist.copy(), prediction=prediction)
