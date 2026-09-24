"""Storage abstraction (port) for the Memory Engine.

The application depends on :class:`MemoryRepository`, never on a concrete
store. SQLite, Postgres or an in-memory implementation may be swapped behind
it without touching the service.

User isolation is enforced at the interface level: every read/write operation
is scoped by ``user_id``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.common.ids import MemoryId, UserId
from contracts.memory.memory import Memory

from .filters import MemoryQuery


@runtime_checkable
class MemoryRepository(Protocol):
    """Port that any memory store must implement."""

    def create(self, memory: Memory) -> Memory: ...

    def get(self, user_id: UserId, memory_id: MemoryId) -> Memory | None: ...

    def update(self, memory: Memory) -> Memory: ...

    def delete(self, user_id: UserId, memory_id: MemoryId) -> bool: ...

    def search(self, query: MemoryQuery) -> list[Memory]: ...