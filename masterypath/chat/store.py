"""General (non-mastery) chat sessions, persisted in ``data/chat.db``."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    model_id    TEXT NOT NULL DEFAULT '',
    kb_ids      TEXT NOT NULL DEFAULT '[]',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    attachments TEXT NOT NULL DEFAULT '[]',
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages ON messages(session_id, id);
"""


class UnknownSession(KeyError):
    pass


def _session_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "session_id": row["session_id"],
        "title": row["title"],
        "model_id": row["model_id"],
        "kb_ids": json.loads(row["kb_ids"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _message_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "attachments": json.loads(row["attachments"] or "[]"),
        "created_at": row["created_at"],
    }


class ChatStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "chat.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- sessions ---------------------------------------------------------
    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            out = []
            for row in rows:
                session = _session_row(row)
                session["message_count"] = self._conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE session_id=?",
                    (session["session_id"],),
                ).fetchone()[0]
                last = self._conn.execute(
                    "SELECT content FROM messages WHERE session_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (session["session_id"],),
                ).fetchone()
                session["last_message"] = last["content"] if last else ""
                out.append(session)
            return out

    def create_session(
        self,
        *,
        title: str = "",
        model_id: str = "",
        kb_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        session_id = f"c{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions(session_id,title,model_id,kb_ids,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (session_id, title, model_id, json.dumps(kb_ids or []), now, now),
            )
            self._conn.commit()
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if row is None:
            raise UnknownSession(session_id)
        return _session_row(row)

    def update_session(self, session_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        session = self.get_session(session_id)
        title = str(fields.get("title", session["title"]) or "")
        model_id = str(fields.get("model_id", session["model_id"]) or "")
        kb_ids = fields.get("kb_ids", session["kb_ids"])
        if not isinstance(kb_ids, list):
            kb_ids = session["kb_ids"]
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET title=?,model_id=?,kb_ids=?,updated_at=? "
                "WHERE session_id=?",
                (title, model_id, json.dumps(kb_ids), time.time(), session_id),
            )
            self._conn.commit()
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM sessions WHERE session_id=?", (session_id,)
            )
            self._conn.execute(
                "DELETE FROM messages WHERE session_id=?", (session_id,)
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise UnknownSession(session_id)

    # -- messages ---------------------------------------------------------
    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [_message_row(row) for row in rows]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages(session_id,role,content,attachments,created_at) "
                "VALUES(?,?,?,?,?)",
                (session_id, role, content, json.dumps(attachments or []), now),
            )
            self._conn.execute(
                "UPDATE sessions SET updated_at=? WHERE session_id=?",
                (now, session_id),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM messages WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
        return _message_row(row)


__all__ = ["ChatStore", "UnknownSession"]
