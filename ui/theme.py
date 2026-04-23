"""Central Qt stylesheet for the desktop app."""

from __future__ import annotations

from PyQt5.QtWidgets import QApplication

QSS_THEME = """
QDialog,
QMainWindow,
QWidget#loginDialogRoot,
QWidget#registerDialogRoot,
QWidget#mainWindowRoot {
    background-color: #08131d;
    color: #e6f3ff;
}

QWidget {
    color: #d8edf8;
}

QLabel {
    color: #d8edf8;
    background-color: transparent;
}

QWidget#loginCard,
QWidget#registerCard,
QWidget#pageCard,
QWidget#summaryCard,
QLabel#summaryCard {
    background-color: rgba(11, 28, 43, 0.9);
    color: #e6f3ff;
    border: 1px solid #1f4d66;
    border-radius: 18px;
    padding: 14px;
}

QLabel#loginTitle,
QLabel#registerTitle,
QLabel#pageTitle {
    color: #f3fbff;
    font-size: 22px;
    font-weight: 700;
}

QLabel#pageIntro,
QLabel#sectionTitle {
    color: #93bad0;
}

QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 600;
}

QLineEdit,
QComboBox,
QTableView,
QTableWidget {
    background-color: #102739;
    alternate-background-color: #163247;
    color: #e6f3ff;
    border: 1px solid #29536b;
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: #17405b;
    selection-color: #ffffff;
}

QTableWidget {
    gridline-color: #163347;
}

QTableWidget::item,
QTableView::item {
    color: #e6f3ff;
    background-color: transparent;
}

QTableWidget::item:selected,
QTableView::item:selected {
    color: #ffffff;
    background-color: #1d4d6b;
}

QHeaderView::section {
    background-color: #102638;
    color: #9fc4d7;
    border: none;
    border-bottom: 1px solid #29536b;
    padding: 8px 10px;
}

QPushButton,
QToolButton {
    background-color: #10283b;
    color: #d5edf9;
    border: 1px solid #2d5c78;
    border-radius: 10px;
    padding: 8px 14px;
}

QPushButton:hover,
QToolButton:hover {
    background-color: #15354c;
}

QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1cc8ff, stop:1 #39d8c0);
    color: #052232;
    border: none;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #44d4ff, stop:1 #63e4cd);
}

QPushButton#secondaryButton {
    background-color: #0f2436;
}

QPushButton#dangerButton {
    background-color: #4f2130;
    color: #ffeaf0;
    border: 1px solid #8e4155;
}

QPushButton#dangerButton:hover {
    background-color: #663040;
}

QToolButton#passwordToggleButton {
    min-width: 56px;
    background-color: #10283b;
    color: #8ae6ff;
    border: 1px solid #2d5c78;
}

QCheckBox#rememberPasswordCheckbox {
    color: #b7d6e6;
    spacing: 8px;
}

QTabWidget::pane {
    border: 1px solid #1f4d66;
    border-radius: 18px;
    background-color: rgba(9, 22, 34, 0.96);
    top: -1px;
}

QTabBar::tab {
    background-color: #0d2030;
    color: #8fb8cd;
    border: 1px solid #1f4d66;
    border-bottom: none;
    padding: 10px 18px;
    margin-right: 6px;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}

QTabBar::tab:selected {
    background-color: #17384f;
    color: #f3fbff;
    font-weight: 700;
}

QStatusBar#mainStatusBar {
    color: #a5c8da;
    background-color: #08131d;
}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the shared stylesheet to the QApplication instance."""

    app.setStyleSheet(QSS_THEME)
