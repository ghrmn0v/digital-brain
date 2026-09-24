"""MemoryService — the public Memory Engine API.

Owns the memory lifecycle deterministically (no LLM):

    candidate -> validate -> classify -> confidence -> importance
              -> temporal setup -> persist -> conflict resolution

Future Context / Reasoning modules consume this service; they must NOT touch
the repository directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from contracts.common.ids import MemoryId, UserId
from contracts.common.types import Source
from contracts.memory.memory import Memory, MemoryStatus, MemoryType
from uuid import uuid4

from .candidate import MemoryCandidate
from .classifier import MemoryClassifier
from .confidence import resolve_confidence
from .conflicts import conflict_key, supersede_with
from .exceptions import MemoryNotFoundError, MemoryValidationError
from .filters import MemoryQuery, MemoryStatusFilter
from .importance import baseline_importance
from .repository import MemoryRepository
from .temporal import now_utc, validate_memory_temporal

_UNSET = object()


def _new_memory_id() -> str:
    return f"mem_{uuid4().hex[:16]}"


class MemoryService:
    """Deterministic Memory Engine lifecycle and retrieval API."""

    def __init__(
        self,
        repository: MemoryRepository,
        *,
        classifier: MemoryClassifier | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(repository, MemoryRepository):
            raise TypeError("repository must implement MemoryRepository")
        self._repo = repository
        self._classifier = classifier or MemoryClassifier()
        self._now_fn = now or now_utc

    # -- lifecycle ------------------------------------------------------------
    def create_memory(self, candidate: MemoryCandidate) -> Memory:
        """Validate, classify, score, persist and conflict-resolve a memory."""
        if not candidate.content or not candidate.content.strip():
            raise MemoryValidationError("content must be a non-empty string")

        now = self._now_fn()
        memory_type = self._classifier.classify(candidate)
        confidence = resolve_confidence(candidate)
        importance = baseline_importance(candidate, confidence)

        memory = Memory(
            version="v1",
            memory_id=candidate.memory_id or _new_memory_id(),
            user_id=candidate.user_id,
            type=memory_type,
            content=candidate.content,
            source=candidate.source or Source(provider="system"),
            confidence=confidence,
            importance=importance,
            created_at=now,
            updated_at=now,
            valid_from=candidate.valid_from or now,
            valid_until=None,
            status=MemoryStatus.ACTIVE,
            superseded_by=None,
            related_people=list(candidate.related_people),
            related_events=list(candidate.related_events),
            metadata=dict(candidate.metadata),
        )
        validate_memory_temporal(memory)

        self._repo.create(memory)
        self._resolve_conflicts(memory)
        return memory

    def _resolve_conflicts(self, new_memory: Memory) -> None:
        """Supersede every existing ACTIVE memory in the same conflict domain."""
        key = conflict_key(new_memory)
        if key is None:
            return
        candidates = self._repo.search(
            MemoryQuery(
                user_id=new_memory.user_id,
                conflict_key=key,
                status=MemoryStatusFilter.ACTIVE,
            )
        )
        for old in candidates:
            if old.memory_id == new_memory.memory_id:
                continue
            self._repo.update(supersede_with(old, successor=new_memory))

    # -- reads -----------------------------------------------------------------
    def get_memory(self, user_id: UserId, memory_id: MemoryId) -> Memory:
        memory = self._repo.get(user_id, memory_id)
        if memory is None:
            raise MemoryNotFoundError(
                f"memory {memory_id!r} does not exist for user {user_id!r}"
            )
        return memory

    def list_memories(self, query: MemoryQuery) -> list[Memory]:
        return self._repo.search(query)

    def retrieve_relevant_memories(
        self,
        user_id: UserId,
        *,
        memory_type: MemoryType | None = None,
        person_id: str | None = None,
        importance_min: float | None = None,
        text: str | None = None,
        limit: int = 20,
    ) -> list[Memory]:
        """ACTIVE memories ranked by importance, then by recency.

        This is the deterministic stand-in for future semantic retrieval
        (Phase 4 can replace the ranking without changing the signature).
        """
        memories = self._repo.search(
            MemoryQuery(
                user_id=user_id,
                memory_type=memory_type,
                person_id=person_id,
                status=MemoryStatusFilter.ACTIVE,
                importance_min=importance_min,
                text=text,
                limit=None,
            )
        )
        memories.sort(
            key=lambda m: (
                -m.importance,
                -m.updated_at.timestamp(),
                m.memory_id,
            )
        )
        return memories[:limit]

    # -- updates --------------------------------------------------------------
    def update_memory(
        self,
        user_id: UserId,
        memory_id: MemoryId,
        *,
        content: str | None = None,
        confidence: float | None = None,
        importance: float | None = None,
        valid_until: datetime | object = _UNSET,
        status: MemoryStatus | None = None,
        superseded_by: str | object = _UNSET,
        related_people: list[str] | None = None,
        related_events: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        """Apply partial updates to an existing memory (updated_at refreshed)."""
        existing = self.get_memory(user_id, memory_id)
        updates: dict[str, Any] = {}

        if content is not None:
            if not content.strip():
                raise MemoryValidationError("content must be a non-empty string")
            updates["content"] = content
        if confidence is not None:
            updates["confidence"] = confidence
        if importance is not None:
            updates["importance"] = importance
        if valid_until is not _UNSET:
            updates["valid_until"] = valid_until
        if status is not None:
            updates["status"] = status
        if superseded_by is not _UNSET:
            updates["superseded_by"] = superseded_by
        if related_people is not None:
            updates["related_people"] = list(related_people)
        if related_events is not None:
            updates["related_events"] = list(related_events)
        if metadata is not None:
            merged = dict(existing.metadata)
            merged.update(metadata)
            updates["metadata"] = merged
        if not updates:
            raise MemoryValidationError("no fields to update")

        updates["updated_at"] = self._now_fn()
        updated = existing.model_copy(update=updates)
        validate_memory_temporal(updated)
        return self._repo.update(updated)

    def supersede_memory(
        self,
        user_id: UserId,
        memory_id: MemoryId,
        *,
        superseded_by: str | None = None,
        happened_at: datetime | None = None,
    ) -> Memory:
        """Manually supersede a memory (idempotent; the old record is kept)."""
        existing = self.get_memory(user_id, memory_id)
        if existing.status == MemoryStatus.SUPERSEDED:
            return existing

        ended = self._now_fn() if happened_at is None else happened_at
        if ended < existing.valid_from:
            ended = existing.valid_from
        if existing.valid_until is not None and existing.valid_until < ended:
            ended = existing.valid_until

        updated = existing.model_copy(
            update={
                "status": MemoryStatus.SUPERSEDED,
                "superseded_by": superseded_by,
                "valid_until": ended,
                "updated_at": self._now_fn(),
            }
        )
        validate_memory_temporal(updated)
        return self._repo.update(updated)

    def delete_memory(self, user_id: UserId, memory_id: MemoryId) -> bool:
        return self._repo.delete(user_id, memory_id)