"""Tests for the shared Qt theme layer."""

from __future__ import annotations

from ui.theme import apply_theme


def test_apply_theme_sets_shared_stylesheet_markers(qapp) -> None:
    apply_theme(qapp)

    stylesheet = qapp.styleSheet()
    assert "#loginCard" in stylesheet
    assert "QTabBar::tab:selected" in stylesheet
    assert "#passwordToggleButton" in stylesheet
