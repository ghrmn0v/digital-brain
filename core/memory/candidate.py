"""Input type for the Memory Engine lifecycle.

A :class:`MemoryCandidate` is a relaxed view of the Phase 0 ``Memory``
contract: the engine-computed fields (``type``, ``confidence``, ``importance``)
may be omitted so the engine can classify and score them deterministically.

The stored entity is always a full ``contracts.memory.Memory``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contracts.common.ids import EventId, MemoryId, PersonId, UserId
from contracts.common.types import Confidence, Source
from contracts.memory.memory import Memory, MemoryType


@dataclass(frozen=True)
class MemoryCandidate:
    """A memory to be validated, classified, scored and persisted."""

    content: str
    user_id: UserId
    type: MemoryType | None = None
    source: Source | None = None
    confidence: Confidence | None = None
    importance: float | None = None
    memory_id: MemoryId | None = None
    valid_from: datetime | None = None
    related_people: list[PersonId] = field(default_factory=list)
    related_events: list[EventId] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_memory(cls, memory: Memory) -> "MemoryCandidate":
        """Adapt an existing Memory contract into a candidate (replays the pipeline)."""
        return cls(
            content=memory.content,
            user_id=memory.user_id,
            type=memory.type,
            source=memory.source,
            confidence=memory.confidence,
            importance=memory.importance,
            memory_id=memory.memory_id,
            valid_from=memory.valid_from,
            related_people=list(memory.related_people),
            related_events=list(memory.related_events),
            metadata=dict(memory.metadata),
        )