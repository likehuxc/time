"""Pytest fixtures for Qt-based tests."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication for tests without opening a visible window."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
