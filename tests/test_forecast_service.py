"""Regression tests for forecast horizon mapping."""

from __future__ import annotations

from services.forecast_service import horizon_to_steps


def test_horizon_to_steps_supports_thirty_day_forecasts() -> None:
    assert horizon_to_steps("30d") == 720
