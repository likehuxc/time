"""Tests for the shared Qt theme layer."""

from __future__ import annotations

from ui.theme import apply_theme


def test_apply_theme_sets_shared_stylesheet_markers(qapp) -> None:
    apply_theme(qapp)

    stylesheet = qapp.styleSheet()
    assert "#loginCard" in stylesheet
    assert "QTabBar::tab:selected" in stylesheet
    assert "#passwordToggleButton" in stylesheet


def test_apply_theme_explicitly_styles_label_foreground_on_dark_surfaces(qapp) -> None:
    apply_theme(qapp)

    stylesheet = qapp.styleSheet()
    assert "QLabel {" in stylesheet
    assert "QLabel#summaryCard" in stylesheet


def test_apply_theme_styles_alternating_table_rows_for_dark_mode(qapp) -> None:
    apply_theme(qapp)

    stylesheet = qapp.styleSheet()
    assert "alternate-background-color" in stylesheet


def test_apply_theme_styles_combo_popup_for_dark_mode(qapp) -> None:
    apply_theme(qapp)

    stylesheet = qapp.styleSheet()
    assert "QComboBox QAbstractItemView" in stylesheet


def test_apply_theme_styles_context_menus_for_dark_mode(qapp) -> None:
    apply_theme(qapp)

    stylesheet = qapp.styleSheet()
    assert "QMenu {" in stylesheet
    assert "QMenu::item:selected" in stylesheet
