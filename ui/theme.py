"""Central Qt stylesheet for the desktop app."""

from __future__ import annotations

from PyQt5.QtWidgets import QApplication

QSS_THEME = """
QWidget#loginCard,
QDialog,
QMainWindow {
    background-color: #f5f7fb;
    color: #1f2937;
}

QLineEdit,
QComboBox,
QTableView,
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #dbeafe;
    selection-color: #111827;
}

QPushButton,
QToolButton {
    background-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 14px;
}

QPushButton:hover,
QToolButton:hover {
    background-color: #dbeafe;
}

QPushButton#primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}

QPushButton#primaryButton:hover {
    background-color: #1d4ed8;
}

QToolButton#passwordToggleButton {
    background-color: #eef2ff;
    border: 1px solid #c7d2fe;
    color: #4338ca;
}

QTabWidget::pane {
    border: 1px solid #cbd5e1;
    border-top: none;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    padding: 8px 14px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1d4ed8;
    font-weight: 600;
}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the shared stylesheet to the QApplication instance."""

    app.setStyleSheet(QSS_THEME)
