"""Wiring for a production ingestion service.

:func:`build_ingestion` creates ONE sqlite connection (autocommit mode) shared
by the memory store and the receipt store, both with ``auto_commit=False``,
and drives both behind a single :class:`~.transaction.SqliteTransaction`. That
is what makes an ingest atomic: memories and the receipt commit together or
not at all.

Standalone wiring (repos with their own connections + NullTransaction) is
still possible for tests and simple embeddings; it just commits per store.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.memory import MemoryService, SqliteMemoryRepository

from .processor import DeterministicEventProcessor, EventProcessor
from .service import IngestionService
from .sqlite_receipt_repository import SqliteEventReceiptRepository
from .transaction import SqliteTransaction


def build_ingestion(
    path: str | Path = "data/brain.sqlite3",
    *,
    processor: EventProcessor | None = None,
) -> IngestionService:
    """Build an atomic ingestion service over one SQLite database file."""
    db_path = str(path)
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    memory_repo = SqliteMemoryRepository(connection=conn, auto_commit=False)
    receipt_repo = SqliteEventReceiptRepository(connection=conn, auto_commit=False)
    memory_service = MemoryService(memory_repo)

    return IngestionService(
        memory_service,
        receipt_repo,
        processor=processor or DeterministicEventProcessor(),
        transaction=SqliteTransaction(conn),
        finalizer=conn.close,
    )