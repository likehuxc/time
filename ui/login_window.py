"""Login dialog for local multi-account desktop auth."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
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

from app.paths import RUNTIME_DIR
from services.auth_service import AuthError, authenticate_user
from services.user_store import UserStore, UserStoreError
from ui.password_field import PasswordField
from ui.register_dialog import RegisterDialog


class LoginWindow(QDialog):
    """Authenticate against local user records in ``runtime/users.json``."""

    login_succeeded = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录")
        self.setModal(True)
        self.resize(440, 280)

        self._users_path = RUNTIME_DIR / "users.json"
        self._store = UserStore(self._users_path)
        self._storage_ready = self._ensure_storage_dir()
        self.current_username: str | None = None

        title = QLabel("家庭用电量预测系统")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")

        self._username = QLineEdit(self)
        self._username.setPlaceholderText("请输入用户名")

        self._password_field = PasswordField("请输入密码", self)
        self._password = self._password_field.line_edit

        form = QFormLayout()
        form.addRow("用户名", self._username)
        form.addRow("密码", self._password_field)

        self._login_btn = QPushButton("登录")
        self._login_btn.setDefault(True)
        self._login_btn.clicked.connect(self._try_login)
        self._password.returnPressed.connect(self._try_login)

        self._register_btn = QPushButton("注册")
        self._register_btn.clicked.connect(self._on_register_clicked)

        self._login_btn.setEnabled(self._storage_ready)
        self._register_btn.setEnabled(self._storage_ready)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._login_btn)
        buttons.addWidget(self._register_btn)

        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addSpacing(8)
        root.addLayout(form)
        root.addStretch(1)
        root.addLayout(buttons)

    def _on_register_clicked(self) -> None:
        if not self._storage_ready:
            return
        dialog = RegisterDialog(self._store, self)
        if dialog.exec_() == QDialog.Accepted and dialog.created_username:
            self._username.setText(dialog.created_username)
            self._password.clear()
            self._password.setFocus()

    def _show_storage_error(self, action: str, _exc: OSError) -> None:
        QMessageBox.critical(
            self,
            "本地账户错误",
            f"无法{action}，请检查本地账户目录是否可用。",
        )

    def _show_store_exception(self, exc: UserStoreError) -> None:
        QMessageBox.critical(self, "本地账户错误", str(exc))

    def _ensure_storage_dir(self) -> bool:
        try:
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._show_storage_error("初始化本地账户目录", exc)
            return False
        return True

    def _try_login(self) -> None:
        if not self._storage_ready:
            return
        try:
            user = authenticate_user(
                self._store, self._username.text(), self._password.text()
            )
        except AuthError as exc:
            message = str(exc)
            if message not in {
                "请输入用户名。",
                "请输入密码。",
                "该账号已禁用。",
                "用户不存在。",
            }:
                message = "用户名或密码错误。"
            QMessageBox.warning(self, "登录失败", message)
            self._password.clear()
            self._password_field.conceal()
            self._password.setFocus()
            return
        except UserStoreError as exc:
            self._show_store_exception(exc)
            return

        self.current_username = user.username
        self.login_succeeded.emit(user.username)
        self.accept()
