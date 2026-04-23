"""Local user account storage backed by ``runtime/users.json``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class UserRecord:
    """Serializable local account record."""

    username: str
    password_digest: str
    created_at: str
    updated_at: str
    disabled: bool = False


class UserStoreError(RuntimeError):
    """Raised when the local account storage cannot be read or written."""


class UserStore:
    """Load and persist local accounts from a JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def list_users(self) -> list[UserRecord]:
        payload = self._read_payload()
        users = payload.get("users", [])
        if not isinstance(users, list):
            raise UserStoreError("本地账户数据格式无效。")
        return [self._record_from_dict(item) for item in users]

    def find_user(self, username: str) -> UserRecord | None:
        target = username.casefold()
        for user in self.list_users():
            if user.username.casefold() == target:
                return user
        return None

    def save_user(self, user: UserRecord) -> None:
        users = self.list_users()
        replaced = False
        next_users: list[UserRecord] = []
        target = user.username.casefold()
        for existing in users:
            if existing.username.casefold() == target:
                next_users.append(user)
                replaced = True
            else:
                next_users.append(existing)
        if not replaced:
            next_users.append(user)
        self._write_payload({"users": [asdict(item) for item in next_users]})

    def delete_user(self, username: str) -> bool:
        users = self.list_users()
        target = username.casefold()
        next_users = [user for user in users if user.username.casefold() != target]
        if len(next_users) == len(users):
            return False
        self._write_payload({"users": [asdict(item) for item in next_users]})
        return True

    def _read_payload(self) -> dict[str, object]:
        if not self._path.is_file():
            return {"users": []}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UserStoreError("本地账户数据已损坏，无法读取。") from exc
        except OSError as exc:
            raise UserStoreError("无法读取本地账户数据。") from exc
        if not isinstance(raw, dict):
            raise UserStoreError("本地账户数据格式无效。")
        return raw

    def _write_payload(self, payload: dict[str, object]) -> None:
        temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temp_path.replace(self._path)
        except OSError as exc:
            raise UserStoreError("无法写入本地账户数据。") from exc

    def _record_from_dict(self, item: object) -> UserRecord:
        if not isinstance(item, dict):
            raise UserStoreError("本地账户数据格式无效。")
        try:
            username = item["username"]
            password_digest = item["password_digest"]
            created_at = item["created_at"]
            updated_at = item["updated_at"]
            disabled = item.get("disabled", False)
        except KeyError as exc:
            raise UserStoreError("本地账户数据缺少必要字段。") from exc
        if not all(
            isinstance(value, str)
            for value in (username, password_digest, created_at, updated_at)
        ):
            raise UserStoreError("本地账户数据字段类型无效。")
        if not isinstance(disabled, bool):
            raise UserStoreError("本地账户数据字段类型无效。")
        return UserRecord(
            username=username,
            password_digest=password_digest,
            created_at=created_at,
            updated_at=updated_at,
            disabled=disabled,
        )
