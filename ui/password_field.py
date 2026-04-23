"""Reusable password input with a visibility toggle button."""

from __future__ import annotations

from PyQt5.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget


class PasswordField(QWidget):
    """Wrap a password line edit with a text toggle."""

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.line_edit = QLineEdit(self)
        self.line_edit.setObjectName("passwordLineEdit")
        self.line_edit.setEchoMode(QLineEdit.Password)
        self.line_edit.setPlaceholderText(placeholder)

        self.toggle_button = QToolButton(self)
        self.toggle_button.setObjectName("passwordToggleButton")
        self.toggle_button.setText("显示")
        self.toggle_button.setToolTip("显示密码")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.clicked.connect(self._toggle_visibility)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.toggle_button)

    def _toggle_visibility(self, checked: bool) -> None:
        self.line_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.toggle_button.setText("隐藏" if checked else "显示")
        self.toggle_button.setToolTip("隐藏密码" if checked else "显示密码")

    def conceal(self) -> None:
        self.toggle_button.setChecked(False)
        self.line_edit.setEchoMode(QLineEdit.Password)
        self.toggle_button.setText("显示")
        self.toggle_button.setToolTip("显示密码")
