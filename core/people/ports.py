"""People Intelligence ports (abstractions People Intelligence depends on).

People Intelligence owns NO memory storage. It reads people/preference facts
from Memory Engine records and persists preferences through the same engine.
``core.memory.MemoryService`` satisfies this port unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.memory.memory import Memory

from core.memory.candidate import MemoryCandidate
from core.memory.filters import MemoryQuery


@runtime_checkable
class PeopleMemory(Protocol):
    """Read-only memory access for people/relationship/preference queries."""

    def list_memories(self, query: MemoryQuery) -> list[Memory]: ...


@runtime_checkable
class PeopleMemoryWriter(Protocol):
    """Write path used to persist a preference through the Memory Engine."""

    def create_memory(self, candidate: MemoryCandidate) -> Memory: ...