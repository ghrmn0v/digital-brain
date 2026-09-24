"""Retrieval filters for the Memory Engine.

Deterministic filtering only — no embeddings, no vector search. The
``MemoryQuery`` is the seam a Phase 4 semantic search can extend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from contracts.common.ids import PersonId, UserId
from contracts.memory.memory import MemoryType


class MemoryStatusFilter(str, Enum):
    ACTIVE = "active"  # status=ACTIVE and not expired
    HISTORICAL = "historical"  # superseded/archived or expired
    ANY = "any"


@dataclass(frozen=True)
class MemoryQuery:
    """A deterministic retrieval query. ``user_id`` is always required."""

    user_id: UserId
    memory_type: MemoryType | None = None
    person_id: PersonId | None = None
    status: MemoryStatusFilter = MemoryStatusFilter.ACTIVE
    conflict_key: str | None = field(
        default=None, repr=False
    )  # internal: used by conflict resolution
    importance_min: float | None = None
    source_provider: str | None = None
    text: str | None = None  # lexical substring match on content
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int | None = 100
    offset: int = 0