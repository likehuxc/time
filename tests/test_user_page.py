"""Regression tests for the user page and shared password field."""

from __future__ import annotations

from PyQt5.QtWidgets import QLineEdit, QMessageBox

from services.login_preferences import load_remembered_login, save_remembered_login
from services.user_store import UserRecord, UserStore
from ui.pages.user_page import UserPage
from ui.password_field import PasswordField


def test_password_field_uses_text_toggle_labels_and_resets_on_conceal(qapp) -> None:
    field = PasswordField("Password")

    assert field.line_edit.objectName() == "passwordLineEdit"
    assert field.toggle_button.objectName() == "passwordToggleButton"
    assert field.toggle_button.text() == "显示"
    assert field.line_edit.echoMode() == QLineEdit.Password

    field.toggle_button.click()

    assert field.toggle_button.text() == "隐藏"
    assert field.line_edit.echoMode() == QLineEdit.Normal

    field.conceal()

    assert field.toggle_button.text() == "显示"
    assert field.line_edit.echoMode() == QLineEdit.Password


def test_deleting_current_account_clears_matching_remembered_login(
    qapp, monkeypatch, tmp_path
) -> None:
    users_path = tmp_path / "users.json"
    store = UserStore(users_path)
    store.save_user(
        UserRecord(
            username="alice",
            password_digest="digest",
            created_at="2026-04-23T00:00:00",
            updated_at="2026-04-23T00:00:00",
        )
    )

    remembered_login_path = tmp_path / "remembered_login.json"
    save_remembered_login(remembered_login_path, username="alice", password="secret")

    page = UserPage(store=store, remembered_login_path=remembered_login_path)
    page.set_current_user("alice")

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr("ui.pages.user_page.clear_prediction_records", lambda **kwargs: 0)

    page._on_delete_account_clicked()

    assert store.find_user("alice") is None
    assert load_remembered_login(remembered_login_path) is None


def test_user_page_does_not_show_local_storage_explainer_cards(qapp) -> None:
    page = UserPage()
    label_texts = [
        label.text()
        for label in page.findChildren(type(page._current_user))
    ]

    assert all("当前模式" not in text for text in label_texts)
    assert all("凭据存储" not in text for text in label_texts)
