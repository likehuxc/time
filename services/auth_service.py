"""Password hashing plus local account register/login rules."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Final

from services.user_store import UserRecord, UserStore

_ALGO: Final[str] = "pbkdf2_sha256"
_ITERATIONS: Final[int] = 310_000
_SALT_BYTES: Final[int] = 16
_SALT_HEX_LEN: Final[int] = _SALT_BYTES * 2
_HASH_NAME: Final[str] = "sha256"
_DIGEST_BYTES: Final[int] = 32
_DIGEST_HEX_LEN: Final[int] = _DIGEST_BYTES * 2
_MIN_USERNAME_LEN: Final[int] = 3
_MAX_USERNAME_LEN: Final[int] = 32
_MIN_PASSWORD_LEN: Final[int] = 8
_MAX_SUPPORTED_ITERATIONS: Final[int] = 1_000_000


class AuthError(ValueError):
    """Raised when registration or login validation fails."""


def hash_password(raw_password: str) -> str:
    """Return a storable digest string for *raw_password* (random salt per call)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        raw_password.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_DIGEST_BYTES,
    )
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(raw_password: str, digest: str) -> bool:
    """Return True if *raw_password* matches *digest* from :func:`hash_password`."""
    try:
        algo, iters_s, salt_hex, expected_hex = digest.split("$", 3)
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    try:
        iterations = int(iters_s)
    except ValueError:
        return False
    if iterations < 1 or iterations > _MAX_SUPPORTED_ITERATIONS:
        return False
    if len(salt_hex) != _SALT_HEX_LEN or len(expected_hex) != _DIGEST_HEX_LEN:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        raw_password.encode("utf-8"),
        salt,
        iterations,
        dklen=_DIGEST_BYTES,
    )
    return hmac.compare_digest(actual, expected)


def register_user(
    store: UserStore, username: str, password: str, confirm_password: str
) -> UserRecord:
    """Register a new local user after validating the fields."""
    normalized_username = _normalize_username(username)
    _validate_passwords(password, confirm_password)
    if _username_exists(store, normalized_username):
        raise AuthError("用户名已存在。")
    now = datetime.now().isoformat(timespec="seconds")
    user = UserRecord(
        username=normalized_username,
        password_digest=hash_password(password),
        created_at=now,
        updated_at=now,
        disabled=False,
    )
    store.save_user(user)
    return user


def authenticate_user(store: UserStore, username: str, password: str) -> UserRecord:
    """Authenticate a stored local account."""
    normalized_username = _normalize_username(username)
    if not password:
        raise AuthError("请输入密码。")
    user = None
    for existing in store.list_users():
        if existing.username.casefold() == normalized_username.casefold():
            user = existing
            break
    if user is None:
        raise AuthError("用户不存在。")
    if user.disabled:
        raise AuthError("该账号已禁用。")
    if not verify_password(password, user.password_digest):
        raise AuthError("用户名或密码错误。")
    return user


def update_password(
    store: UserStore,
    username: str,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> UserRecord:
    """Update the password for an existing local user."""
    user = authenticate_user(store, username, current_password)
    _validate_passwords(new_password, confirm_password)
    updated_user = UserRecord(
        username=user.username,
        password_digest=hash_password(new_password),
        created_at=user.created_at,
        updated_at=datetime.now().isoformat(timespec="seconds"),
        disabled=user.disabled,
    )
    store.save_user(updated_user)
    return updated_user


def delete_user_account(store: UserStore, username: str) -> None:
    """Delete an existing local account."""
    normalized_username = _normalize_username(username)
    if not store.delete_user(normalized_username):
        raise AuthError("用户不存在。")


def _normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise AuthError("请输入用户名。")
    if len(normalized) < _MIN_USERNAME_LEN:
        raise AuthError(f"用户名长度不能少于 {_MIN_USERNAME_LEN} 位。")
    if len(normalized) > _MAX_USERNAME_LEN:
        raise AuthError(f"用户名长度不能超过 {_MAX_USERNAME_LEN} 位。")
    if any(ch.isspace() for ch in normalized):
        raise AuthError("用户名不能包含空白字符。")
    return normalized


def _validate_passwords(password: str, confirm_password: str) -> None:
    if not password:
        raise AuthError("请输入密码。")
    if len(password) < _MIN_PASSWORD_LEN:
        raise AuthError(f"密码长度不能少于 {_MIN_PASSWORD_LEN} 位。")
    if password != confirm_password:
        raise AuthError("两次输入的密码不一致。")


def _username_exists(store: UserStore, username: str) -> bool:
    target = username.casefold()
    return any(user.username.casefold() == target for user in store.list_users())
