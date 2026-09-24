"""SQLite-backed :class:`MemoryRepository`.

The simplest reliable local persistence for Phase 1. Replaces the contract
behind the ``MemoryRepository`` port.

Times are stored as UTC ISO-8601 strings; ``related_people`` is normalized
into a join table; ``related_events`` and ``metadata`` are JSON columns. The
derived ``conflict_key`` is stored and indexed so conflict detection is a fast
indexed query.

Thread-safety: a single connection guarded by a lock (``check_same_thread``
disabled) is enough for the local single-process scope of Phase 1.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from contracts.common.types import Source
from contracts.memory.memory import Memory, MemoryStatus, MemoryType

from .conflicts import conflict_key
from .exceptions import MemoryNotFoundError, MemoryValidationError
from .filters import MemoryQuery, MemoryStatusFilter
from .temporal import now_utc


def default_db_path() -> Path:
    """Repository-root ``data/brain.sqlite3`` (repo root = two levels up)."""
    return Path(__file__).resolve().parents[2] / "data" / "brain.sqlite3"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id        TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    type             TEXT NOT NULL,
    content          TEXT NOT NULL,
    source_provider  TEXT NOT NULL,
    source_component TEXT,
    source_version   TEXT,
    confidence       REAL NOT NULL,
    importance       REAL NOT NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    valid_from       TEXT NOT NULL,
    valid_until      TEXT,
    status           TEXT NOT NULL,
    superseded_by    TEXT,
    conflict_key     TEXT,
    related_events   TEXT NOT NULL DEFAULT '[]',
    metadata         TEXT NOT NULL DEFAULT '{}',
    contract_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_people (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    person_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mem_user_status ON memories(user_id, status);
CREATE INDEX IF NOT EXISTS idx_mem_user_type   ON memories(user_id, type);
CREATE INDEX IF NOT EXISTS idx_mem_ckey        ON memories(user_id, conflict_key);
CREATE INDEX IF NOT EXISTS idx_people_memory   ON memory_people(memory_id);
CREATE INDEX IF NOT EXISTS idx_people_person   ON memory_people(person_id);
"""

_INSERT = """
INSERT INTO memories (
    memory_id, user_id, type, content,
    source_provider, source_component, source_version,
    confidence, importance,
    created_at, updated_at, valid_from, valid_until,
    status, superseded_by, conflict_key, related_events, metadata,
    contract_version
) VALUES (
    :memory_id, :user_id, :type, :content,
    :source_provider, :source_component, :source_version,
    :confidence, :importance,
    :created_at, :updated_at, :valid_from, :valid_until,
    :status, :superseded_by, :conflict_key, :related_events, :metadata,
    :contract_version
)
"""

_COLUMNS = """
    memory_id, user_id, type, content,
    source_provider, source_component, source_version,
    confidence, importance,
    created_at, updated_at, valid_from, valid_until,
    status, superseded_by, related_events, metadata, contract_version
"""


def _dt(value: datetime) -> str:
    return value.isoformat()


def _pdt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _escape_like(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


class SqliteMemoryRepository:
    """SQLite implementation of :class:`MemoryRepository`."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = str(path) if path is not None else str(default_db_path())
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- helpers ------------------------------------------------------------
    def _people_of(self, memory_id: str) -> list[str]:
        cur = self._conn.execute(
            "SELECT person_id FROM memory_people WHERE memory_id = ? ORDER BY id",
            (memory_id,),
        )
        return [row["person_id"] for row in cur.fetchall()]

    def _replace_people(self, cur: sqlite3.Cursor, memory: Memory) -> None:
        cur.execute("DELETE FROM memory_people WHERE memory_id = ?", (memory.memory_id,))
        cur.executemany(
            "INSERT INTO memory_people (memory_id, person_id) VALUES (?, ?)",
            [(memory.memory_id, person_id) for person_id in memory.related_people],
        )

    def _memory_to_params(self, memory: Memory) -> dict[str, Any]:
        return {
            "memory_id": memory.memory_id,
            "user_id": memory.user_id,
            "type": memory.type.value,
            "content": memory.content,
            "source_provider": memory.source.provider,
            "source_component": memory.source.component,
            "source_version": memory.source.version,
            "confidence": memory.confidence,
            "importance": memory.importance,
            "created_at": _dt(memory.created_at),
            "updated_at": _dt(memory.updated_at),
            "valid_from": _dt(memory.valid_from),
            "valid_until": _dt(memory.valid_until) if memory.valid_until else None,
            "status": memory.status.value,
            "superseded_by": memory.superseded_by,
            "conflict_key": conflict_key(memory),
            "related_events": json.dumps(memory.related_events),
            "metadata": json.dumps(memory.metadata),
            "contract_version": memory.version,
        }

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        memory = Memory(
            version=row["contract_version"],
            memory_id=row["memory_id"],
            user_id=row["user_id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            source=Source(
                provider=row["source_provider"],
                component=row["source_component"],
                version=row["source_version"],
            ),
            confidence=float(row["confidence"]),
            importance=float(row["importance"]),
            created_at=_pdt(row["created_at"]),
            updated_at=_pdt(row["updated_at"]),
            valid_from=_pdt(row["valid_from"]),
            valid_until=_pdt(row["valid_until"]) if row["valid_until"] else None,
            status=MemoryStatus(row["status"]),
            superseded_by=row["superseded_by"],
            related_events=json.loads(row["related_events"]),
            metadata=json.loads(row["metadata"]),
        )
        return memory.model_copy(update={"related_people": self._people_of(memory.memory_id)})

    # -- port implementation ----------------------------------------------
    def create(self, memory: Memory) -> Memory:
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(_INSERT, self._memory_to_params(memory))
            except sqlite3.IntegrityError as exc:
                raise MemoryValidationError(
                    f"memory_id {memory.memory_id!r} already exists"
                ) from exc
            self._replace_people(cur, memory)
            self._conn.commit()
        return memory

    def get(self, user_id: str, memory_id: str) -> Memory | None:
        with self._lock:
            cur = self._conn.execute(
                f"SELECT {_COLUMNS} FROM memories WHERE user_id = ? AND memory_id = ?",
                (user_id, memory_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_memory(row)

    def update(self, memory: Memory) -> Memory:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE memories SET
                    user_id = :user_id,
                    type = :type,
                    content = :content,
                    source_provider = :source_provider,
                    source_component = :source_component,
                    source_version = :source_version,
                    confidence = :confidence,
                    importance = :importance,
                    created_at = :created_at,
                    updated_at = :updated_at,
                    valid_from = :valid_from,
                    valid_until = :valid_until,
                    status = :status,
                    superseded_by = :superseded_by,
                    conflict_key = :conflict_key,
                    related_events = :related_events,
                    metadata = :metadata,
                    contract_version = :contract_version
                WHERE memory_id = :memory_id
                """,
                self._memory_to_params(memory),
            )
            if cur.rowcount == 0:
                raise MemoryNotFoundError(f"memory {memory.memory_id!r} not found")
            self._replace_people(cur, memory)
            self._conn.commit()
        return memory

    def delete(self, user_id: str, memory_id: str) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "DELETE FROM memories WHERE user_id = ? AND memory_id = ?",
                (user_id, memory_id),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def search(self, query: MemoryQuery) -> list[Memory]:
        where = ["m.user_id = :user_id"]
        params: dict[str, Any] = {"user_id": query.user_id, "now": _dt(now_utc())}

        if query.memory_type is not None:
            where.append("m.type = :memory_type")
            params["memory_type"] = query.memory_type.value
        if query.conflict_key is not None:
            where.append("m.conflict_key = :conflict_key")
            params["conflict_key"] = query.conflict_key
        if query.importance_min is not None:
            where.append("m.importance >= :importance_min")
            params["importance_min"] = query.importance_min
        if query.source_provider is not None:
            where.append("m.source_provider = :source_provider")
            params["source_provider"] = query.source_provider
        if query.text is not None:
            where.append("m.content LIKE :text ESCAPE '\\'")
            params["text"] = f"%{_escape_like(query.text)}%"
        if query.created_after is not None:
            where.append("m.created_at >= :created_after")
            params["created_after"] = _dt(query.created_after)
        if query.created_before is not None:
            where.append("m.created_at <= :created_before")
            params["created_before"] = _dt(query.created_before)
        if query.person_id is not None:
            where.append(
                "EXISTS (SELECT 1 FROM memory_people p "
                "WHERE p.memory_id = m.memory_id AND p.person_id = :person_id)"
            )
            params["person_id"] = query.person_id
        if query.status == MemoryStatusFilter.ACTIVE:
            where.append(
                "m.status = :active_status "
                "AND (m.valid_until IS NULL OR m.valid_until > :now)"
            )
            params["active_status"] = MemoryStatus.ACTIVE.value
        elif query.status == MemoryStatusFilter.HISTORICAL:
            where.append(
                "(m.status != :active_status "
                "OR (m.valid_until IS NOT NULL AND m.valid_until <= :now))"
            )
            params["active_status"] = MemoryStatus.ACTIVE.value

        sql = f"SELECT m.{_COLUMNS} FROM memories m WHERE {' AND '.join(where)}"
        sql += " ORDER BY m.created_at DESC, m.memory_id ASC"
        if query.limit is not None:
            sql += " LIMIT :limit OFFSET :offset"
            params["limit"] = query.limit
            params["offset"] = query.offset

        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
        return [self._row_to_memory(row) for row in rows]