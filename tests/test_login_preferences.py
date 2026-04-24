"""Tests for remembered-login persistence."""

from __future__ import annotations

import json
import os

from services.login_preferences import (
    clear_remembered_login,
    clear_remembered_login_for_username,
    load_remembered_login,
    save_remembered_login,
)


def test_missing_file_returns_none(tmp_path) -> None:
    assert load_remembered_login(tmp_path / "remembered_login.json") is None


def test_qt_platform_is_offscreen_before_fixture_use() -> None:
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_save_load_round_trip(tmp_path) -> None:
    path = tmp_path / "remembered_login.json"

    saved = save_remembered_login(path, username="alice", password="secret")
    loaded = load_remembered_login(path)

    assert loaded == saved
    assert loaded is not None
    assert loaded.remember_password is True
    assert loaded.username == "alice"
    assert loaded.password == "secret"
    assert loaded.updated_at


def test_corrupt_payload_returns_none(tmp_path) -> None:
    path = tmp_path / "remembered_login.json"
    path.write_text(json.dumps({"username": "alice"}), encoding="utf-8")

    assert load_remembered_login(path) is None


def test_invalid_utf8_returns_none(tmp_path) -> None:
    path = tmp_path / "remembered_login.json"
    path.write_bytes(b"\xff\xfe\xff")

    assert load_remembered_login(path) is None


def test_clear_by_username_only_removes_matching_user(tmp_path) -> None:
    path = tmp_path / "remembered_login.json"
    save_remembered_login(path, username="alice", password="secret")

    clear_remembered_login_for_username(path, username="bob")

    assert load_remembered_login(path) is not None

    clear_remembered_login_for_username(path, username="alice")

    assert load_remembered_login(path) is None


def test_clear_remembered_login_removes_file(tmp_path) -> None:
    path = tmp_path / "remembered_login.json"
    save_remembered_login(path, username="alice", password="secret")

    clear_remembered_login(path)

    assert not path.exists()
    assert load_remembered_login(path) is None
