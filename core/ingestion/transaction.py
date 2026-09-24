"""Transaction boundary for the ingestion pipeline.

Persistence order inside an ingest: process -> create memories -> record the
receipt. The receipt is the LAST write, so it is a marker of success; the
memory write and the receipt write must either both commit or both roll back.

The factory wires a real :class:`SqliteTransaction` (BEGIN IMMEDIATE /
commit / rollback) around ONE shared sqlite connection used by both the
receipt store and the memory store. Independent wiring uses
:class:`NullTransaction`, where each store commits on its own — usable, but
not atomic (never silently partial: the worker still cannot crash between the
two and leave a receipt without its memory, because the receipt is written
last and is only written after memories succeed).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Protocol


class Transaction(Protocol):
    """Boundary that groups a set of writes into one atomic unit."""

    def __enter__(self) -> "Transaction": ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any: ...


class NullTransaction:
    """No-op boundary for standalone (per-store, auto-commit) wiring."""

    def __enter__(self) -> "NullTransaction":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return False


class SqliteTransaction:
    """Real SQLite transaction over a shared, autocommit-mode connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def __enter__(self) -> "SqliteTransaction":
        self._conn.execute("BEGIN IMMEDIATE")
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        return False