"""SQLite backing for ingestion receipts.

A dedicated ``ingestion_receipts`` table, physically separate from the memory
tables, keyed by ``(identity_kind, identity_key, user_id)``. It keeps partial
duplicates of the same logical event across restarts.

Supports the same connection-sharing/``auto_commit`` contract as the memory
repository so a single factory can wrap one shared sqlite connection in one
transaction.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .deduplication import EventIdentity
from .models import IngestionReceipt

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_receipts (
    identity_kind TEXT NOT NULL,
    identity_key  TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    event_id      TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    payload_hash  TEXT NOT NULL,
    ingested_at   TEXT NOT NULL,
    PRIMARY KEY (identity_kind, identity_key, user_id)
);
"""


def default_receipt_db_path() -> Path:
    return Path("data") / "receipts.sqlite3"


class SqliteEventReceiptRepository:
    """SQLite receipt store behind the EventReceiptRepository port."""

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
            self._path = str(path) if path is not None else str(default_receipt_db_path())
            if self._path != ":memory:":
                Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._owns_connection = True
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
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

    # -- port implementation ----------------------------------------------
    def has_seen(self, identity: EventIdentity) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM ingestion_receipts "
                "WHERE identity_kind = ? AND identity_key = ? AND user_id = ?",
                identity.composite,
            )
            return cur.fetchone() is not None

    def get(self, identity: EventIdentity) -> IngestionReceipt | None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM ingestion_receipts "
                "WHERE identity_kind = ? AND identity_key = ? AND user_id = ?",
                identity.composite,
            )
            row = cur.fetchone()
        if row is None:
            return None
        return IngestionReceipt(
            event_id=row["event_id"],
            event_type=row["event_type"],
            payload_hash=row["payload_hash"],
            ingested_at=_parse_dt(row["ingested_at"]),
            identity_kind=row["identity_kind"],
            identity_key=row["identity_key"].split(":", 1)[1],
            user_id=row["user_id"],
        )

    def record(self, identity: EventIdentity, receipt: IngestionReceipt) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO ingestion_receipts "
                "(identity_kind, identity_key, user_id, event_id, event_type, "
                " payload_hash, ingested_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    identity.kind,
                    identity.key,
                    identity.user_id,
                    receipt.event_id,
                    receipt.event_type,
                    receipt.payload_hash,
                    receipt.ingested_at.isoformat(),
                ),
            )
            self._commit()


def _parse_dt(value: str) -> "datetime":
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)