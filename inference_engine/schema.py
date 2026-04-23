"""Validate CSV/table columns against template_schema.json."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from app.config import load_template_schema


@dataclass(frozen=True)
class ColumnValidationResult:
    is_valid: bool
    filtered_frame: pd.DataFrame
    missing_required: list[str]
    dropped_columns: list[str]


def validate_and_filter_columns(
    frame: pd.DataFrame,
    schema: Optional[dict[str, Any]] = None,
) -> ColumnValidationResult:
    """Keep only schema-allowed columns; report missing required and drops."""
    spec = schema if schema is not None else load_template_schema()
    required: list[str] = list(spec["required_columns"])
    optional: list[str] = list(spec.get("optional_columns", []))
    allowed = set(required) | set(optional)

    present = set(frame.columns)
    missing_required = [c for c in required if c not in present]
    dropped_columns = sorted(present - allowed)

    kept: list[str] = []
    for c in required:
        if c in present:
            kept.append(c)
    for c in optional:
        if c in present and c not in kept:
            kept.append(c)

    filtered_frame = frame[kept].copy()
    is_valid = len(missing_required) == 0
    return ColumnValidationResult(
        is_valid=is_valid,
        filtered_frame=filtered_frame,
        missing_required=missing_required,
        dropped_columns=dropped_columns,
    )
