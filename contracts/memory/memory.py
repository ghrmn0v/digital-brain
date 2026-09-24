"""Brain-owned memory contract.

Only the DATA CONTRACT. The Memory Engine is implemented in a later phase.

This contract already covers the lifecycle a memory needs:
    - ``valid_from`` / ``valid_until`` decide whether a memory is *currently*
      valid without destroying its history.
    - ``status`` + ``superseded_by`` record the lineage between overlapping
      memories.

Example — person changed employer:
    old "person works at Company A"
        valid_until=2026-03-01, status=SUPERSEDED, superseded_by="mem_2"
    new "person works at Company B"
        valid_from=2026-03-02, status=ACTIVE, valid_until=None

Both remain retrievable; only the ACTIVE one is treated as current truth.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..common.ids import EventId, MemoryId, PersonId, UserId
from ..common.types import (
    Confidence,
    ContractVersion,
    Importance,
    Source,
    UtcDateTime,
)


class MemoryType(str, Enum):
    """Coarse taxonomy of what a memory is. Additive; unknown value = error."""

    FACT = "fact"
    EPISODE = "episode"
    INTERACTION = "interaction"
    RELATIONSHIP = "relationship"
    PREFERENCE = "preference"
    EVENT = "event"
    OBSERVATION = "observation"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class Memory(BaseModel):
    """A single Brain-owned memory record."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    memory_id: MemoryId
    user_id: UserId
    type: MemoryType
    content: str
    source: Source
    confidence: Confidence
    importance: Importance
    created_at: UtcDateTime
    updated_at: UtcDateTime
    valid_from: UtcDateTime
    valid_until: UtcDateTime | None = Field(
        default=None, description="None = currently valid"
    )
    status: MemoryStatus = MemoryStatus.ACTIVE
    superseded_by: MemoryId | None = None
    related_people: list[PersonId] = Field(default_factory=list)
    related_events: list[EventId] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)