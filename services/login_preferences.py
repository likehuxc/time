"""Persistence for the single remembered-login record."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.paths import RUNTIME_DIR

DEFAULT_REMEMBERED_LOGIN_PATH = RUNTIME_DIR / "remembered_login.json"


@dataclass(frozen=True)
class RememberedLogin:
    """Serializable remembered-login state."""

    remember_password: bool
    username: str
    password: str
    updated_at: str


def load_remembered_login(
    path: Path = DEFAULT_REMEMBERED_LOGIN_PATH,
) -> RememberedLogin | None:
    """Load the remembered-login record from *path* if it exists."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        remember_password = payload["remember_password"]
        username = payload["username"]
        password = payload["password"]
        updated_at = payload["updated_at"]
    except KeyError:
        return None
    if not isinstance(remember_password, bool):
        return None
    if not all(isinstance(value, str) for value in (username, password, updated_at)):
        return None
    return RememberedLogin(
        remember_password=remember_password,
        username=username,
        password=password,
        updated_at=updated_at,
    )


def save_remembered_login(
    path: Path = DEFAULT_REMEMBERED_LOGIN_PATH, *, username: str, password: str
) -> RememberedLogin:
    """Persist a remembered-login record to *path*."""
    record = RememberedLogin(
        remember_password=True,
        username=username,
        password=password,
        updated_at=datetime.now().isoformat(timespec="seconds"),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def clear_remembered_login(path: Path = DEFAULT_REMEMBERED_LOGIN_PATH) -> None:
    """Remove the remembered-login file if it exists."""
    try:
        path.unlink()
    except FileNotFoundError:
        return


def clear_remembered_login_for_username(
    path: Path = DEFAULT_REMEMBERED_LOGIN_PATH, username: str = ""
) -> None:
    """Remove the remembered-login file when it belongs to *username*."""
    if not username:
        return
    record = load_remembered_login(path)
    if record is None:
        return
    if record.username.casefold() != username.casefold():
        return
    clear_remembered_login(path)
