"""SQLite persistence for prediction records."""

import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from app.paths import RUNTIME_DIR

DEFAULT_DB_PATH = RUNTIME_DIR / "forecast.db"

_CREATE_PREDICTION_RECORDS_SQL = """
CREATE TABLE IF NOT EXISTS prediction_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    username TEXT NOT NULL DEFAULT '',
    model_id TEXT,
    horizon_key TEXT,
    template_path TEXT,
    output_path TEXT,
    metrics_json TEXT
);
"""


def _reset_prediction_record_sequence(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("prediction_records",))


def _ensure_username_column(conn: sqlite3.Connection) -> None:
    columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(prediction_records)")
    }
    if "username" not in columns:
        conn.execute(
            "ALTER TABLE prediction_records ADD COLUMN username TEXT NOT NULL DEFAULT ''"
        )


def init_prediction_records(db_path: Optional[Path] = None) -> None:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(_CREATE_PREDICTION_RECORDS_SQL)
        _ensure_username_column(conn)
        conn.commit()


def claim_legacy_prediction_records(
    username: str, *, db_path: Optional[Path] = None
) -> int:
    """Assign legacy rows without username to the first logged-in user."""
    path = db_path or DEFAULT_DB_PATH
    init_prediction_records(path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE prediction_records
            SET username = ?
            WHERE username = ''
            """,
            (username,),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def save_prediction_record(
    *,
    username: str,
    model_id: str,
    horizon_key: str,
    template_path: str = "",
    output_path: str = "",
    metrics_json: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """插入一条预测记录；返回新行 ``id``（``created_at`` 由数据库默认填充）。"""
    path = db_path or DEFAULT_DB_PATH
    init_prediction_records(path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO prediction_records (
                username, model_id, horizon_key, template_path, output_path, metrics_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, model_id, horizon_key, template_path, output_path, metrics_json),
        )
        conn.commit()
        rid = cur.lastrowid
    return int(rid)


def list_prediction_records(
    *,
    username: str,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> List[dict[str, Any]]:
    """Return recent rows from ``prediction_records`` (newest first)."""
    path = db_path or DEFAULT_DB_PATH
    init_prediction_records(path)
    cap = max(1, min(int(limit), 10_000))
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT id, created_at, username, model_id, horizon_key, template_path, output_path, metrics_json
            FROM prediction_records
            WHERE username = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (username, cap),
        )
        return [dict(row) for row in cur.fetchall()]


def update_prediction_record_output_path(
    record_id: int,
    output_path: str,
    *,
    username: str,
    db_path: Optional[Path] = None,
) -> int:
    """Update one prediction record output path; return affected row count."""
    path = db_path or DEFAULT_DB_PATH
    init_prediction_records(path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            """
            UPDATE prediction_records
            SET output_path = ?
            WHERE id = ? AND username = ?
            """,
            (output_path, int(record_id), username),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def delete_prediction_record(
    record_id: int,
    *,
    username: str,
    db_path: Optional[Path] = None,
) -> int:
    """Delete one prediction record by id; return affected row count."""
    return delete_prediction_records([record_id], username=username, db_path=db_path)


def delete_prediction_records(
    record_ids: list[int],
    *,
    username: str,
    db_path: Optional[Path] = None,
) -> int:
    """Delete multiple prediction records; return affected row count."""
    ids = [int(record_id) for record_id in record_ids]
    if not ids:
        return 0
    path = db_path or DEFAULT_DB_PATH
    init_prediction_records(path)
    placeholders = ", ".join("?" for _ in ids)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            f"DELETE FROM prediction_records WHERE username = ? AND id IN ({placeholders})",
            (username, *tuple(ids)),
        )
        deleted = int(cur.rowcount or 0)
        conn.commit()
        return deleted


def clear_prediction_records(
    *,
    username: str,
    db_path: Optional[Path] = None,
) -> int:
    """Delete all prediction records; return affected row count."""
    path = db_path or DEFAULT_DB_PATH
    init_prediction_records(path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            "DELETE FROM prediction_records WHERE username = ?", (username,)
        )
        remaining = conn.execute(
            "SELECT COUNT(1) FROM prediction_records"
        ).fetchone()
        if remaining is not None and int(remaining[0]) == 0:
            _reset_prediction_record_sequence(conn)
        conn.commit()
        return int(cur.rowcount or 0)
