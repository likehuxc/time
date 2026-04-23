"""Register dialog for local multi-account desktop login."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.auth_service import AuthError, register_user
from services.user_store import UserStore, UserStoreError
from ui.password_field import PasswordField


class RegisterDialog(QDialog):
    """Collect registration details and create a local user account."""

    def __init__(self, store: UserStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self.created_username: str | None = None

        self.setWindowTitle("注册账号")
        self.setModal(True)
        self.resize(420, 260)

        title = QLabel("创建本地账号")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")

        self._username = QLineEdit(self)
        self._username.setPlaceholderText("请输入用户名")

        self._password_field = PasswordField("请输入密码", self)
        self._password = self._password_field.line_edit

        self._confirm_password_field = PasswordField("请再次输入密码", self)
        self._confirm_password = self._confirm_password_field.line_edit
        self._confirm_password.returnPressed.connect(self._submit)

        form = QFormLayout()
        form.addRow("用户名", self._username)
        form.addRow("密码", self._password_field)
        form.addRow("确认密码", self._confirm_password_field)

        self._submit_btn = QPushButton("注册")
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
            user = register_user(
                self._store,
                self._username.text(),
                self._password.text(),
                self._confirm_password.text(),
            )
        except AuthError as exc:
            QMessageBox.warning(self, "注册失败", str(exc))
            self._password.clear()
            self._confirm_password.clear()
            self._password_field.conceal()
            self._confirm_password_field.conceal()
            return
        except UserStoreError as exc:
            QMessageBox.critical(self, "本地账户错误", str(exc))
            return

        self.created_username = user.username
        QMessageBox.information(self, "注册成功", "注册成功，请返回登录。")
        self.accept()
