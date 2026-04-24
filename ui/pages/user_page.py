"""用户中心页面。"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.paths import RUNTIME_DIR
from services.auth_service import AuthError, delete_user_account
from services.login_preferences import (
    DEFAULT_REMEMBERED_LOGIN_PATH,
    clear_remembered_login_for_username,
)
from services.record_service import clear_prediction_records
from services.user_store import UserStore
from ui.change_password_dialog import ChangePasswordDialog


class UserPage(QWidget):
    """本地多用户会话信息与账号操作。"""

    logout_requested = pyqtSignal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        store: UserStore | None = None,
        remembered_login_path: Path = DEFAULT_REMEMBERED_LOGIN_PATH,
    ) -> None:
        super().__init__(parent)
        self._store = store if store is not None else UserStore(RUNTIME_DIR / "users.json")
        self._remembered_login_path = remembered_login_path
        self._current_username: str | None = None

        title = QLabel("用户中心")
        title.setObjectName("pageTitle")

        self._current_user = QLabel("当前登录：未登录")
        self._current_user.setObjectName("summaryCard")
        self._current_user.setTextFormat(Qt.PlainText)
        self._current_user.setWordWrap(True)

        actions_title = QLabel("账号操作")
        actions_title.setObjectName("sectionTitle")

        change_password = QPushButton("修改密码")
        change_password.setObjectName("secondaryButton")
        change_password.setFocusPolicy(Qt.NoFocus)
        change_password.clicked.connect(self._on_change_password_clicked)

        logout = QPushButton("退出登录")
        logout.setObjectName("secondaryButton")
        logout.setFocusPolicy(Qt.NoFocus)
        logout.clicked.connect(self.logout_requested.emit)

        delete_account = QPushButton("注销账号")
        delete_account.setObjectName("dangerButton")
        delete_account.setFocusPolicy(Qt.NoFocus)
        delete_account.clicked.connect(self._on_delete_account_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self._current_user)
        layout.addWidget(actions_title)
        layout.addWidget(change_password)
        layout.addWidget(logout)
        layout.addWidget(delete_account)
        layout.addStretch(1)

    def _on_change_password_clicked(self) -> None:
        if not self._current_username:
            return
        dialog = ChangePasswordDialog(self._store, self._current_username, self)
        if dialog.exec_() == QDialog.Accepted:
            self.logout_requested.emit()

    def set_current_user(self, username: str) -> None:
        self._current_username = username
        self._current_user.setText(f"当前登录：{username}")

    def clear_current_user(self) -> None:
        self._current_username = None
        self._current_user.setText("当前登录：未登录")

    def _on_delete_account_clicked(self) -> None:
        if not self._current_username:
            return
        choice = QMessageBox.question(
            self,
            "注销账号",
            "确定要注销当前账号吗？该账号及其历史记录将被永久删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if choice != QMessageBox.Yes:
            return
        try:
            existing_user = self._store.find_user(self._current_username)
            delete_user_account(self._store, self._current_username)
            clear_prediction_records(username=self._current_username)
            clear_remembered_login_for_username(
                self._remembered_login_path, username=self._current_username
            )
        except AuthError as exc:
            QMessageBox.warning(self, "注销失败", str(exc))
            return
        except Exception:
            try:
                restored = False
                if "existing_user" in locals() and existing_user is not None:
                    self._store.save_user(existing_user)
                    restored = True
                QMessageBox.warning(
                    self,
                    "注销失败",
                    (
                        "注销过程中发生错误，当前账号已恢复，请稍后重试。"
                        if restored
                        else "注销过程中发生错误，账号状态未确认，请检查本地账户数据。"
                    ),
                )
            except Exception:
                QMessageBox.warning(
                    self,
                    "注销失败",
                    "注销过程中发生错误，且账号恢复失败，请立即检查本地账户数据。",
                )
            return

        QMessageBox.information(self, "注销成功", "当前账号已注销，请重新登录。")
        self.logout_requested.emit()
