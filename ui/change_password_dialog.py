"""Change-password dialog for the local desktop account flow."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.auth_service import AuthError, update_password
from services.user_store import UserStore, UserStoreError
from ui.password_field import PasswordField


class ChangePasswordDialog(QDialog):
    """Let the current local user change their password."""

    def __init__(
        self, store: UserStore, username: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._username = username

        self.setWindowTitle("修改密码")
        self.setModal(True)
        self.resize(440, 280)

        title = QLabel(f"修改账号密码：{username}")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")

        self._current_password_field = PasswordField("请输入当前密码", self)
        self._current_password = self._current_password_field.line_edit
        self._new_password_field = PasswordField("请输入新密码", self)
        self._new_password = self._new_password_field.line_edit
        self._confirm_password_field = PasswordField("请再次输入新密码", self)
        self._confirm_password = self._confirm_password_field.line_edit
        self._confirm_password.returnPressed.connect(self._submit)

        form = QFormLayout()
        form.addRow("当前密码", self._current_password_field)
        form.addRow("新密码", self._new_password_field)
        form.addRow("确认新密码", self._confirm_password_field)

        self._submit_btn = QPushButton("确认修改")
        self._submit_btn.setDefault(True)
        self._submit_btn.clicked.connect(self._submit)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self._submit_btn)
        actions.addWidget(self._cancel_btn)

        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addLayout(form)
        root.addStretch(1)
        root.addLayout(actions)

    def _submit(self) -> None:
        try:
            update_password(
                self._store,
                self._username,
                self._current_password.text(),
                self._new_password.text(),
                self._confirm_password.text(),
            )
        except AuthError as exc:
            QMessageBox.warning(self, "修改失败", str(exc))
            self._current_password.clear()
            self._new_password.clear()
            self._confirm_password.clear()
            self._current_password_field.conceal()
            self._new_password_field.conceal()
            self._confirm_password_field.conceal()
            return
        except UserStoreError as exc:
            QMessageBox.critical(self, "本地账户错误", str(exc))
            return

        QMessageBox.information(self, "修改成功", "密码已更新，请使用新密码登录。")
        self.accept()
