"""Resample time series to hourly frequency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

import pandas as pd

DATE_COL = "date"
TARGET_FREQUENCY = "1h"
MISSING_TIME_CONTEXT_ERROR = (
    "CSV 缺少 date 时间列时，必须同时提供 start_time 和 source_freq，"
    "系统才能重建时间轴并统一到小时级。"
)
INVALID_DATE_COLUMN_ERROR = (
    "CSV 中的 date 列无法解析为有效时间，请检查日期格式后重试。"
)


@dataclass(frozen=True)
class HourlyNormalizationResult:
    frame: pd.DataFrame
    source_frequency: str
    target_frequency: str


def normalize_to_hourly(
    frame: pd.DataFrame,
    start_time: Optional[Union[str, pd.Timestamp]] = None,
    source_freq: Optional[str] = None,
) -> HourlyNormalizationResult:
    """Resample numeric columns to 1h using mean; keep ``date`` as a column."""
    df = frame.copy()

    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], format="mixed", errors="coerce")
        if df[DATE_COL].isna().any():
            raise ValueError(INVALID_DATE_COLUMN_ERROR)
        df = df.sort_values(by=DATE_COL)
        idx = pd.DatetimeIndex(df[DATE_COL])
        df = df.drop(columns=[DATE_COL])
        df.index = idx
        src = source_freq
        if src is None:
            try:
                inferred = pd.infer_freq(df.index)
            except ValueError:
                inferred = None
            src = inferred if inferred is not None else "irregular"
    else:
        if start_time is None or source_freq is None:
            raise ValueError(MISSING_TIME_CONTEXT_ERROR)
        anchor = pd.Timestamp(start_time)
        rng = pd.date_range(start=anchor, periods=len(df), freq=source_freq)
        df.index = rng
        src = source_freq

    numeric_df = df.select_dtypes(include="number").copy()
    if numeric_df.empty:
        raise ValueError("没有可聚合的数值列用于重采样")

    resampled = numeric_df.resample(TARGET_FREQUENCY).mean()
    resampled = resampled.dropna(how="all")
    resampled.index.name = DATE_COL
    out = resampled.reset_index()

    preferred = [c for c in ("WHE", DATE_COL) if c in out.columns]
    rest = [c for c in out.columns if c not in preferred]
    out = out[preferred + rest]

    return HourlyNormalizationResult(
        frame=out,
        source_frequency=src,
        target_frequency=TARGET_FREQUENCY,
    )
