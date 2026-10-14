"""Workspace-scoped SQLite persistence with compare-and-swap (ADR-006).

Design (spec 01 §五 INV-11/50/51/52, 03 §B):

* Each workspace is its own database *file* — cross-workspace never contends.
* Within a workspace, ``mutate`` runs in one ``BEGIN IMMEDIATE`` transaction:
  load -> apply ``fn`` -> ``UPDATE ... WHERE version = old``. A zero rowcount
  means another writer won; that is a CAS conflict.
* State and events commit together (INV-51); a failed attempt writes neither.
* Optimistic conflicts retry a bounded number of times, then bubble up as
  ``ConcurrentModificationError``. A domain precondition failure raises
  ``PreconditionError`` and is **never** retried (ADR-012).
* WAL + busy_timeout let writers wait instead of raising ``SQLITE_BUSY``.
"""

from __future__ import annotations

import json
import random
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from masterypath.learning.models import (
    InteractionStatus,
    LearningProgress,
    MasteryInteraction,
    QuestionBankEntry,
)

_T = TypeVar("_T")

_ACTIVE_INTERACTION_STATES = (
    InteractionStatus.REGISTERED.value,
    InteractionStatus.AWAITING_INPUT.value,
    InteractionStatus.ANSWERED.value,
)


class ConcurrentModificationError(RuntimeError):
    """Raised when CAS retries are exhausted (INV-11b)."""


class PreconditionError(RuntimeError):
    """Raised when a domain precondition fails; never retried (INV-11c)."""


class Transaction:
    """Passed to ``mutate`` callbacks: mutate ``progress``, ``emit`` events.

    Interaction helpers run on the *same* connection/transaction, so a grade
    that writes the attempt, the evidence and the interaction commits or rolls
    back together (INV-51).
    """

    def __init__(
        self,
        progress: LearningProgress,
        conn: sqlite3.Connection | None = None,
        path_id: str = "",
    ) -> None:
        self.progress = progress
        self.events: list[dict[str, Any]] = []
        self._conn = conn
        self.path_id = path_id

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append({"event_type": event_type, "payload": payload or {}})

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            raise PreconditionError(message)

    # -- interactions (same transaction) ----------------------------------
    def get_interaction(self, interaction_id: str) -> MasteryInteraction | None:
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT data FROM interactions WHERE path_id=? AND interaction_id=?",
            (self.path_id, interaction_id),
        ).fetchone()
        return MasteryInteraction.model_validate_json(row["data"]) if row else None

    def get_open_interaction(self) -> MasteryInteraction | None:
        if self._conn is None:
            return None
        placeholders = ",".join("?" for _ in _ACTIVE_INTERACTION_STATES)
        row = self._conn.execute(
            f"SELECT data FROM interactions WHERE path_id=? AND status IN "
            f"({placeholders}) ORDER BY created_at DESC LIMIT 1",
            (self.path_id, *_ACTIVE_INTERACTION_STATES),
        ).fetchone()
        return MasteryInteraction.model_validate_json(row["data"]) if row else None

    def save_interaction(self, interaction: MasteryInteraction) -> None:
        if self._conn is None:
            raise PreconditionError("no transaction connection")
        interaction.updated_at = time.time()
        self._conn.execute(
            _UPSERT_INTERACTION,
            (
                interaction.interaction_id,
                interaction.path_id,
                interaction.status.value,
                interaction.model_dump_json(),
                interaction.created_at,
                interaction.updated_at,
            ),
        )

    def save_bank_entry(self, entry: QuestionBankEntry) -> None:
        if self._conn is None:
            raise PreconditionError("no transaction connection")
        entry.updated_at = time.time()
        self._conn.execute(
            _UPSERT_BANK,
            (
                entry.entry_id,
                entry.path_id,
                entry.model_dump_json(),
                entry.created_at,
                entry.updated_at,
            ),
        )


_UPSERT_INTERACTION = """
INSERT INTO interactions(interaction_id, path_id, status, data, created_at, updated_at)
VALUES(?,?,?,?,?,?)
ON CONFLICT(interaction_id) DO UPDATE SET
    status=excluded.status, data=excluded.data, updated_at=excluded.updated_at
"""

_UPSERT_BANK = """
INSERT INTO question_bank(entry_id, path_id, data, created_at, updated_at)
VALUES(?,?,?,?,?)
ON CONFLICT(entry_id) DO UPDATE SET
    data=excluded.data, updated_at=excluded.updated_at
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS paths (
    path_id    TEXT PRIMARY KEY,
    version    INTEGER NOT NULL,
    data       TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    path_id    TEXT NOT NULL,
    revision   INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload    TEXT NOT NULL,
    session_id TEXT NOT NULL DEFAULT '',
    turn_id    TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_path_revision ON events(path_id, revision);
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id TEXT PRIMARY KEY,
    path_id        TEXT NOT NULL,
    status         TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_path_status ON interactions(path_id, status);
CREATE TABLE IF NOT EXISTS question_bank (
    entry_id   TEXT PRIMARY KEY,
    path_id    TEXT NOT NULL,
    data       TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bank_path ON question_bank(path_id);
"""


class LearningStore:
    """A workspace's learning database."""

    def __init__(self, base_dir: str | Path, *, retries: int = 3) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "learning.db"
        self.retries = max(1, int(retries))
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- reads -------------------------------------------------------------
    def load(self, path_id: str) -> LearningProgress | None:
        """Read a path, or ``None`` when it does not exist. Never creates."""
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM paths WHERE path_id=?", (path_id,)
            ).fetchone()
        if row is None:
            return None
        return LearningProgress.model_validate_json(row["data"])

    def list_paths(self) -> list[LearningProgress]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM paths ORDER BY updated_at DESC"
            ).fetchall()
        return [LearningProgress.model_validate_json(row["data"]) for row in rows]

    def events_since(self, path_id: str, revision: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE path_id=? AND revision>? ORDER BY id",
                (path_id, revision),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- writes ------------------------------------------------------------
    def create(self, progress: LearningProgress) -> LearningProgress:
        """Insert a brand-new path. Fails if it already exists."""
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                existing = self._conn.execute(
                    "SELECT 1 FROM paths WHERE path_id=?", (progress.path_id,)
                ).fetchone()
                if existing is not None:
                    raise PreconditionError(f"path already exists: {progress.path_id}")
                progress.version = max(1, progress.version)
                progress.updated_at = time.time()
                self._conn.execute(
                    "INSERT INTO paths(path_id, version, data, updated_at) VALUES(?,?,?,?)",
                    (
                        progress.path_id,
                        progress.version,
                        progress.model_dump_json(),
                        progress.updated_at,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return progress

    def mutate(
        self,
        path_id: str,
        fn: Callable[[Transaction], _T],
        *,
        expected_version: int | None = None,
        create_if_missing: bool = False,
    ) -> _T:
        """Apply *fn* atomically with CAS on ``version``.

        ``fn`` must be side-effect free other than mutating ``tx.progress`` and
        calling ``tx.emit`` (INV-11a); events are committed only on success.
        """
        last_error: ConcurrentModificationError | None = None
        for attempt in range(self.retries):
            try:
                return self._attempt(path_id, fn, expected_version, create_if_missing)
            except ConcurrentModificationError as exc:
                last_error = exc
                # jittered backoff to avoid two writers livelocking (ADR-012)
                time.sleep(0.001 * (attempt + 1) + random.random() * 0.002)
        assert last_error is not None
        raise last_error

    def _attempt(
        self,
        path_id: str,
        fn: Callable[[Transaction], _T],
        expected_version: int | None,
        create_if_missing: bool,
    ) -> _T:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT version, data FROM paths WHERE path_id=?", (path_id,)
                ).fetchone()
                if row is None:
                    if not create_if_missing:
                        raise PreconditionError(f"no such path: {path_id}")
                    old_version = None
                    progress = LearningProgress(path_id=path_id)
                else:
                    old_version = int(row["version"])
                    if expected_version is not None and old_version != expected_version:
                        raise PreconditionError(
                            f"version mismatch: expected {expected_version}, "
                            f"found {old_version}"
                        )
                    progress = LearningProgress.model_validate_json(row["data"])
                tx = Transaction(progress, self._conn, path_id)
                result = fn(tx)
                new_version = (old_version or 0) + 1
                progress.version = new_version
                progress.updated_at = time.time()
                if old_version is None:
                    self._conn.execute(
                        "INSERT INTO paths(path_id, version, data, updated_at) "
                        "VALUES(?,?,?,?)",
                        (
                            path_id,
                            new_version,
                            progress.model_dump_json(),
                            progress.updated_at,
                        ),
                    )
                else:
                    cursor = self._conn.execute(
                        "UPDATE paths SET version=?, data=?, updated_at=? "
                        "WHERE path_id=? AND version=?",
                        (
                            new_version,
                            progress.model_dump_json(),
                            progress.updated_at,
                            path_id,
                            old_version,
                        ),
                    )
                    if cursor.rowcount == 0:
                        raise ConcurrentModificationError("cas conflict")
                for event in tx.events:
                    self._conn.execute(
                        "INSERT INTO events(path_id, revision, event_type, payload, "
                        "session_id, turn_id, created_at) VALUES(?,?,?,?,?,?,?)",
                        (
                            path_id,
                            new_version,
                            event["event_type"],
                            json.dumps(event["payload"], ensure_ascii=False),
                            event.get("session_id", ""),
                            event.get("turn_id", ""),
                            time.time(),
                        ),
                    )
                self._conn.commit()
                return result
            except (PreconditionError, ConcurrentModificationError):
                self._conn.rollback()
                raise
            except Exception:
                self._conn.rollback()
                raise

    # -- interactions ------------------------------------------------------
    def save_interaction(self, interaction: MasteryInteraction) -> MasteryInteraction:
        """Insert or update an interaction transaction."""
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                interaction.updated_at = time.time()
                self._conn.execute(
                    "INSERT INTO interactions(interaction_id, path_id, status, data, "
                    "created_at, updated_at) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(interaction_id) DO UPDATE SET "
                    "status=excluded.status, data=excluded.data, updated_at=excluded.updated_at",
                    (
                        interaction.interaction_id,
                        interaction.path_id,
                        interaction.status.value,
                        interaction.model_dump_json(),
                        interaction.created_at,
                        interaction.updated_at,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return interaction

    def get_interaction(
        self, path_id: str, interaction_id: str
    ) -> MasteryInteraction | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM interactions WHERE path_id=? AND interaction_id=?",
                (path_id, interaction_id),
            ).fetchone()
        if row is None:
            return None
        return MasteryInteraction.model_validate_json(row["data"])

    def get_open_interaction(self, path_id: str) -> MasteryInteraction | None:
        """The one non-terminal interaction, or ``None`` (single-slot, INV-02)."""
        placeholders = ",".join("?" for _ in _ACTIVE_INTERACTION_STATES)
        with self._lock:
            row = self._conn.execute(
                f"SELECT data FROM interactions WHERE path_id=? AND status IN "
                f"({placeholders}) ORDER BY created_at DESC LIMIT 1",
                (path_id, *_ACTIVE_INTERACTION_STATES),
            ).fetchone()
        if row is None:
            return None
        return MasteryInteraction.model_validate_json(row["data"])

    # -- question bank -----------------------------------------------------
    def save_bank_entry(self, entry: QuestionBankEntry) -> QuestionBankEntry:
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                entry.updated_at = time.time()
                self._conn.execute(
                    _UPSERT_BANK,
                    (
                        entry.entry_id,
                        entry.path_id,
                        entry.model_dump_json(),
                        entry.created_at,
                        entry.updated_at,
                    ),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return entry

    def get_bank_entry(self, entry_id: str) -> QuestionBankEntry | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM question_bank WHERE entry_id=?", (entry_id,)
            ).fetchone()
        return QuestionBankEntry.model_validate_json(row["data"]) if row else None

    def list_bank_entries(self, path_id: str) -> list[QuestionBankEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM question_bank WHERE path_id=? ORDER BY created_at DESC",
                (path_id,),
            ).fetchall()
        return [QuestionBankEntry.model_validate_json(row["data"]) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


__all__ = [
    "LearningStore",
    "Transaction",
    "ConcurrentModificationError",
    "PreconditionError",
]
