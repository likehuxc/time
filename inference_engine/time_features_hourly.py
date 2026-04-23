"""Hourly timeF features aligned with Time-Series-Library `utils.timefeatures` (freq='h')."""

from __future__ import annotations

import numpy as np
import pandas as pd


def time_features_hourly(
    seq_len: int,
    *,
    start: str = "2000-01-01 00:00:00",
    index: pd.DatetimeIndex | None = None,
) -> np.ndarray:
    """
    Return shape ``(seq_len, 4)``: HourOfDay, DayOfWeek, DayOfMonth, DayOfYear in [-0.5, 0.5].

    Matches ``offsets.Hour`` feature order in ``time_features_from_frequency_str('h')``.
    """
    if index is None:
        idx = pd.date_range(start, periods=seq_len, freq="h")
    else:
        if not isinstance(index, pd.DatetimeIndex):
            raise TypeError("index must be a pandas.DatetimeIndex when provided")
        if len(index) < seq_len:
            raise ValueError(
                f"DatetimeIndex 长度不足：至少需要 {seq_len} 个时间戳（当前 {len(index)} 个）。"
            )
        idx = index[-seq_len:]

    hour = idx.hour / 23.0 - 0.5
    weekday = idx.dayofweek / 6.0 - 0.5
    day = (idx.day - 1) / 30.0 - 0.5
    doy = (idx.dayofyear - 1) / 365.0 - 0.5
    return np.column_stack([hour, weekday, day, doy]).astype(np.float32)
