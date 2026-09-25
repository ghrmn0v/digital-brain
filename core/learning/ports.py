"""Learning ports (Phase 7) — the seams Learning depends on.

The Learning layer owns NO storage. It reads/writes memories through the same
ports People Intelligence uses (``core.memory.MemoryService`` satisfies them
unchanged) and keeps its aggregated state in a ``LearningStateRepository`` that
can later be swapped for a real learning store without API change.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.common.ids import MemoryId, UserId
from contracts.memory.memory import Memory

from core.memory.candidate import MemoryCandidate
from core.memory.filters import MemoryQuery

from .models import LearningStatus


@runtime_checkable
class LearnerMemory(Protocol):
    """Read access to memories (feedback traces, preferences)."""

    def list_memories(self, query: MemoryQuery) -> list[Memory]: ...

    def get_memory(self, user_id: UserId, memory_id: MemoryId) -> Memory: ...


@runtime_checkable
class LearnerMemoryWriter(Protocol):
    """Write path for durable feedback traces."""

    def create_memory(self, candidate: MemoryCandidate) -> Memory: ...


@runtime_checkable
class LearnerMemoryUpdater(Protocol):
    """Deterministic importance adjustment learned from signals."""

    def update_memory(
        self,
        user_id: UserId,
        memory_id: MemoryId,
        *,
        importance: float,
    ) -> Memory: ...


@runtime_checkable
class LearningStateRepository(Protocol):
    """Persistence for the aggregated bounded learning state."""

    def get_status(self, user_id: UserId) -> LearningStatus | None: ...

    def save_status(self, status: LearningStatus) -> LearningStatus: ...