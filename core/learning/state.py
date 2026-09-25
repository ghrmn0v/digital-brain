"""SQLite-backed :class:`LearningStateRepository`.

One row per user holding the bounded aggregate (signal counts, topic
affinities, preference evidence) as JSON. Simple, local and deterministic —
exactly what the MVP needs, with a swap seam for a future learning store.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from contracts.common.ids import UserId

from .models import (
    LearningStatus,
    PreferenceEvidence,
    TopicAffinity,
)


def default_state_path() -> Path:
    """Repository-root ``data/learning.sqlite3`` (repo root = two levels up)."""
    return Path(__file__).resolve().parents[2] / "data" / "learning.sqlite3"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_state (
    user_id            TEXT PRIMARY KEY,
    signal_counts      TEXT NOT NULL,
    topics             TEXT NOT NULL,
    preference_evidence TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    contract_version   TEXT NOT NULL
);
"""

_COLUMNS = "user_id, signal_counts, topics, preference_evidence, updated_at, contract_version"


def _dt(value) -> str:
    return value.isoformat()


def _pdt(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)


class SqliteLearningStateRepository:
    """SQLite implementation of the ``LearningStateRepository`` port."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        connection: sqlite3.Connection | None = None,
        auto_commit: bool = True,
    ) -> None:
        self._lock = threading.Lock()
        if connection is not None:
            self._conn = connection
            self._path = "<shared>"
            self._owns_connection = False
        else:
            self._path = str(path) if path is not None else str(default_state_path())
            if self._path != ":memory:":
                Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._owns_connection = True
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._auto_commit = auto_commit
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            if self._owns_connection:
                self._conn.commit()

    @property
    def sqlite_connection(self) -> sqlite3.Connection:
        return self._conn

    def _commit(self) -> None:
        if self._auto_commit:
            self._conn.commit()

    def close(self) -> None:
        if not self._owns_connection:
            return
        with self._lock:
            self._conn.close()

    # -- port implementation -------------------------------------------------
    def get_status(self, user_id: UserId) -> LearningStatus | None:
        with self._lock:
            cur = self._conn.execute(
                f"SELECT {_COLUMNS} FROM learning_state WHERE user_id = ?",
                (str(user_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        topics = [
            TopicAffinity(**item) for item in json.loads(row["topics"])
        ]
        evidence = [
            PreferenceEvidence(**item)
            for item in json.loads(row["preference_evidence"])
        ]
        return LearningStatus(
            user_id=row["user_id"],
            signal_counts=json.loads(row["signal_counts"]),
            topics=topics,
            preference_evidence=evidence,
            updated_at=_pdt(row["updated_at"]),
        )

    def save_status(self, status: LearningStatus) -> LearningStatus:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO learning_state (user_id, signal_counts, topics,
                    preference_evidence, updated_at, contract_version)
                VALUES (?, ?, ?, ?, ?, 'v1')
                ON CONFLICT(user_id) DO UPDATE SET
                    signal_counts = excluded.signal_counts,
                    topics = excluded.topics,
                    preference_evidence = excluded.preference_evidence,
                    updated_at = excluded.updated_at,
                    contract_version = excluded.contract_version
                """,
                (
                    str(status.user_id),
                    json.dumps(status.signal_counts),
                    json.dumps(
                        [self._dump(item) for item in status.topics]
                    ),
                    json.dumps(
                        [self._dump(item) for item in status.preference_evidence]
                    ),
                    _dt(status.updated_at) if status.updated_at else _dt(_now()),
                ),
            )
            self._commit()
        return status

    @staticmethod
    def _dump(model: BaseModel) -> dict[str, Any]:
        return model.model_dump(mode="json")


def _now() -> datetime:
    return datetime.now(timezone.utc)