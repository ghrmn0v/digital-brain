"""People Intelligence output models (Phase 5).

Everything here is *derived* from the unified Phase 0 ``Person`` contract and
Memory Engine records. There is NO second people database: identity lives in
``PersonId``, facts about a person live in memories. These models are the
readable/reasoning-ready views produced from that memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import EventId, MemoryId, PersonId, UserId
from contracts.common.types import Confidence, Importance, Source, UtcDateTime
from contracts.memory.memory import MemoryStatus, MemoryType

NonEmptyName = Annotated[str, Field(min_length=1, max_length=120)]
NonEmptyValue = Annotated[str, Field(min_length=1, max_length=2000)]


class PreferenceDomain(str, Enum):
    """Modes a developer preference can target (additive)."""

    LANGUAGE = "language"
    CODING_STYLE = "coding_style"
    TESTING = "testing"
    EXPLANATION_DETAIL = "explanation_detail"
    COMMIT_STYLE = "commit_style"
    DEPLOYMENT = "deployment"


class Preference(BaseModel):
    """A single preference owned by the user, traceable to its memory."""

    model_config = ConfigDict(extra="forbid")

    memory_id: MemoryId
    domain: PreferenceDomain | None = None
    name: NonEmptyName
    value: NonEmptyValue
    confidence: Confidence
    importance: Importance


class DeveloperPreferences(BaseModel):
    """Developer-workflow preferences, bucketed by domain (bounded)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    languages: list[Preference] = Field(default_factory=list)
    coding_style: list[Preference] = Field(default_factory=list)
    testing: list[Preference] = Field(default_factory=list)
    explanation_detail: list[Preference] = Field(default_factory=list)
    commit_style: list[Preference] = Field(default_factory=list)
    deployment: list[Preference] = Field(default_factory=list)


class RelationshipFact(BaseModel):
    """A relationship statement about a person the user knows."""

    model_config = ConfigDict(extra="forbid")

    person_id: PersonId
    memory_id: MemoryId
    statement: NonEmptyValue
    confidence: Confidence
    importance: Importance


class InteractionReference(BaseModel):
    """A pointer into the user's interaction history with a person."""

    model_config = ConfigDict(extra="forbid")

    person_id: PersonId
    memory_id: MemoryId
    occurred_at: UtcDateTime
    summary: NonEmptyValue
    source_event_id: EventId | None = None


class PersonFactDurability(str, Enum):
    """How strongly a person memory should be treated over time."""

    DURABLE = "durable"
    TEMPORARY = "temporary"
    UNSPECIFIED = "unspecified"


class PersonSourceTrace(BaseModel):
    """Bounded provenance for one person-related memory."""

    model_config = ConfigDict(extra="forbid")

    source: Source
    source_event_id: EventId | None = None
    correlation_id: str | None = Field(default=None, max_length=256)
    source_event_id_truncated: bool = False
    correlation_id_truncated: bool = False
    related_event_ids: list[EventId] = Field(
        default_factory=list,
        max_length=32,
    )
    evidence: dict[str, Any] = Field(default_factory=dict, max_length=16)


class PersonTimelineEntry(BaseModel):
    """One dated, source-traceable observation in a person's history."""

    model_config = ConfigDict(extra="forbid")

    person_id: PersonId
    memory_id: MemoryId
    memory_type: MemoryType
    status: MemoryStatus
    statement: NonEmptyValue
    statement_truncated: bool = False
    occurred_at: UtcDateTime
    created_at: UtcDateTime
    valid_until: UtcDateTime | None = None
    durability: PersonFactDurability
    confidence: Confidence
    importance: Importance
    provenance: PersonSourceTrace


class PersonTimeline(BaseModel):
    """Bounded historical view of one person, oldest entry first."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    person_id: PersonId
    entries: list[PersonTimelineEntry] = Field(
        default_factory=list,
        max_length=200,
    )
    total_entries: int = Field(ge=0)
    truncated: bool = False
    scan_truncated: bool = False
    person_known: bool = False


class PersonFact(BaseModel):
    """A bounded factual statement aggregated about a person."""

    model_config = ConfigDict(extra="forbid")

    memory_id: MemoryId
    statement: NonEmptyValue
    confidence: Confidence
    importance: Importance


class PersonProfile(BaseModel):
    """Aggregate view of one known person from the user's memories."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    person_id: PersonId
    name: NonEmptyName | None = None
    aliases: list[NonEmptyName] = Field(default_factory=list)
    relationship_facts: list[RelationshipFact] = Field(default_factory=list)
    interactions: list[InteractionReference] = Field(default_factory=list)
    facts: list[PersonFact] = Field(default_factory=list)
    mention_count: int
    last_seen: UtcDateTime | None = None
    memory_ids: list[MemoryId] = Field(default_factory=list)


class PersonSummary(BaseModel):
    """A lightweight row for the list of known people."""

    model_config = ConfigDict(extra="forbid")

    person_id: PersonId
    name: NonEmptyName | None = None
    mention_count: int


class PeopleSummary(BaseModel):
    """People known to the user, ranked by how often they are referenced."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    people: list[PersonSummary] = Field(default_factory=list)


@dataclass(frozen=True)
class PeopleLimits:
    """A resource budget so People Intelligence stays deterministic and small."""

    max_people: int = 50
    max_relationships: int = 10
    max_interactions: int = 10
    max_facts: int = 20
    max_preferences_per_domain: int = 5
    scan_limit: int = 2000
    max_timeline_entries: int = 200

    def __post_init__(self) -> None:
        for name in (
            "max_people",
            "max_relationships",
            "max_interactions",
            "max_facts",
            "max_preferences_per_domain",
            "scan_limit",
            "max_timeline_entries",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_timeline_entries > 200:
            raise ValueError("max_timeline_entries must be at most 200")