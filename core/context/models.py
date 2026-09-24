"""Context models (Phase 4).

``SearchQuery`` is the validated input to the search port. ``ScoredMemory`` is
a deterministic-ranked memory with its traceability info. ``Context`` is the
bounded, reasoning-ready result that Phase 6 will consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import MemoryId, PersonId, UserId
from contracts.common.types import ContractVersion
from contracts.memory.memory import Memory
from core.memory.filters import MemoryStatusFilter
from core.understanding.developer import DeveloperContext
from core.understanding.models import UnderstandingResult

_MAX_KEYWORDS = 24
_MAX_KEYWORD_LEN = 256


class ContextStatus(str, Enum):
    """How the assembled Context was produced."""

    FULL = "full"  # relevant memories were found and included
    CURRENT_ONLY = "current_only"  # search succeeded but nothing was relevant
    DEGRADED = "degraded"  # search failed; only current context is present


class SearchQuery(BaseModel):
    """Validated input for :class:`SemanticSearch` (always user-scoped)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId = Field(min_length=1)
    text: str = Field(default="", max_length=4096)
    keywords: list[str] = Field(
        default_factory=list,
        description="Additional query terms (e.g. understanding entities/topics).",
    )
    repository: str | None = Field(default=None, max_length=512)
    current_file: str | None = Field(default=None, max_length=1024)
    status: MemoryStatusFilter = MemoryStatusFilter.ACTIVE
    top_k: int | None = Field(default=None, ge=1, le=500)

    def clean_keywords(self) -> None:
        cleaned: list[str] = []
        for value in self.keywords:
            if not isinstance(value, str):
                continue
            token = value.strip()[: _MAX_KEYWORD_LEN]
            if token and token not in cleaned:
                cleaned.append(token)
            if len(cleaned) >= _MAX_KEYWORDS:
                break
        self.keywords = cleaned


class ScoredMemory(BaseModel):
    """A memory after deterministic ranking, with full traceability."""

    model_config = ConfigDict(extra="forbid")

    memory: Memory
    score: float = Field(ge=0.0, le=1.0)
    matched_fields: list[str] = Field(default_factory=list)
    ranking_reason: str = Field(default="", max_length=1024)
    repository_match: Literal["exact", "related", "other", "unknown", "none"] | None = (
        None
    )
    file_match: Literal["exact", "same_name", "other", "unknown", "none"] | None = None


class SearchMetadata(BaseModel):
    """Non-secret diagnostics about how a search was executed."""

    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    candidates_considered: int = Field(default=0, ge=0)
    repository_aware: bool = False
    file_aware: bool = False
    status: Literal["ok", "degraded"] = "ok"
    error: str | None = None


class Context(BaseModel):
    """Bounded, reasoning-ready context for a developer's current session.

    References (previous_bug_findings / previous_decisions /
    developer_preferences) are ``MemoryId`` pointers into ``relevant_memories``
    so the persistent representation is never duplicated.
    """

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    context_id: str
    user_id: UserId
    repository: str | None = None
    current_file: str | None = None
    current_line: int | None = Field(default=None, ge=1)
    current_task: str | None = Field(default=None, max_length=4096)

    developer_context: DeveloperContext | None = None
    understanding: UnderstandingResult | None = None

    relevant_memories: list[ScoredMemory] = Field(default_factory=list)
    previous_bug_findings: list[MemoryId] = Field(default_factory=list)
    previous_decisions: list[MemoryId] = Field(default_factory=list)
    developer_preferences: list[MemoryId] = Field(default_factory=list)
    relevant_people: list[PersonId] = Field(default_factory=list)

    search_metadata: SearchMetadata = Field(default_factory=SearchMetadata)
    status: ContextStatus = ContextStatus.CURRENT_ONLY
    fallback_used: bool = False
    created_at: datetime


@dataclass(frozen=True)
class ContextLimits:
    """Deterministic bounds for Context assembly (all zero-safe)."""

    top_memories: int = 8
    top_bug_findings: int = 2
    top_decisions: int = 2
    top_preferences: int = 2
    max_total_memories: int = 16
    category_min_score: float = 0.15
    max_people: int = 12
    max_candidates: int = 500

    def validate(self) -> "ContextLimits":
        if self.top_memories < 0 or self.top_bug_findings < 0:
            raise ValueError("top-* limits must be >= 0")
        if self.top_decisions < 0 or self.top_preferences < 0:
            raise ValueError("top-* limits must be >= 0")
        if self.max_total_memories < 1:
            raise ValueError("max_total_memories must be >= 1")
        if (
            self.top_memories + self.top_bug_findings + self.top_decisions
            + self.top_preferences
            > self.max_total_memories
        ):
            raise ValueError(
                "the sum of per-category limits must not exceed "
                "max_total_memories"
            )
        if not 0.0 <= self.category_min_score <= 1.0:
            raise ValueError("category_min_score must be within [0, 1]")
        if self.max_people < 0:
            raise ValueError("max_people must be >= 0")
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        return self