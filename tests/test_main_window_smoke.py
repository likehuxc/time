"""Smoke coverage for shared desktop window style hooks."""

from __future__ import annotations

from services.user_store import UserStore
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
from ui.register_dialog import RegisterDialog


def test_login_window_exposes_style_hooks(qapp, tmp_path) -> None:
    window = LoginWindow(
        store=UserStore(tmp_path / "users.json"),
        remembered_login_path=tmp_path / "remembered_login.json",
    )

    assert (
        window.findChild(type(window._remember_password), "rememberPasswordCheckbox")
        is window._remember_password
    )
    assert window.findChild(type(window._login_btn), "primaryButton") is window._login_btn


def test_register_dialog_exposes_root_hook(qapp, tmp_path) -> None:
    dialog = RegisterDialog(UserStore(tmp_path / "users.json"))

    assert dialog.objectName() == "registerDialogRoot"


def test_main_window_builds_with_four_tabs(qapp) -> None:
    window = MainWindow()

    assert window._tabs.count() == 4
