"""Load CSV, validate columns, normalize to hourly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from inference_engine.resampler import (
    HourlyNormalizationResult,
    normalize_to_hourly,
)
from inference_engine.schema import ColumnValidationResult, validate_and_filter_columns


@dataclass(frozen=True)
class PreparedCsvResult:
    validation: ColumnValidationResult
    hourly: HourlyNormalizationResult


def load_and_prepare_csv(
    path: Union[str, Path],
    start_time: Optional[Union[str, pd.Timestamp]] = None,
    source_freq: Optional[str] = None,
) -> PreparedCsvResult:
    """read_csv → validate_and_filter_columns → normalize_to_hourly.

    If the CSV does not contain a ``date`` column, callers must provide both
    ``start_time`` and ``source_freq`` so the service can rebuild the timeline
    before normalizing all data to hourly frequency.
    """
    frame = pd.read_csv(path, encoding="utf-8")
    validation = validate_and_filter_columns(frame)
    if not validation.is_valid:
        raise ValueError(
            f"CSV 列校验失败，缺少必填列: {validation.missing_required}"
        )
    hourly = normalize_to_hourly(
        validation.filtered_frame,
        start_time=start_time,
        source_freq=source_freq,
    )
    return PreparedCsvResult(validation=validation, hourly=hourly)
