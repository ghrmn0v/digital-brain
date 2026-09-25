"""Typed result payloads for every Brain API method.

Result models are wire-shaped and bounded — a stable public surface, not a dump
of internal module state. They deliberately reuse the canonical ``contracts.*``
models where those already exist (BrainEvent, BrainDecision, ProposedAction) and
define small flat views for the internal reasoning/people/learning outputs.

The adapter layer (`core.service.api`) fills these from real module results —
a field is copied or counted, never invented.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.brain_events.events import BrainEvent
from contracts.common.ids import UserId
from contracts.common.types import (
    Confidence,
    ContractVersion,
    Importance,
    UtcDateTime,
)
from contracts.decisions.decisions import BrainDecision, ProposedAction


class PingResult(BaseModel):
    """Liveness probe answer."""

    model_config = ConfigDict(extra="forbid")

    service: Literal["digital-brain"] = "digital-brain"
    api_version: Literal["v1"] = "v1"
    ok: bool = True


class DescribeResult(BaseModel):
    """Introspection: method registry + per-method JSON Schemas.

    ``schemas`` maps each ``ApiMethod`` to ``{"params": <json schema>,
    "result": <json schema>}``. External-language SDKs (TS/Java) generate clients
    from these schemas.
    """

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    methods: list[str] = Field(default_factory=list)
    schemas: dict[str, dict[str, Any]] = Field(default_factory=dict)


class IngestionResultWire(BaseModel):
    """Outcome of one ingest call (mirror of ``IngestionResult``)."""

    model_config = ConfigDict(extra="forbid")

    outcome: str
    event_id: str
    user_id: UserId
    correlation_id: str | None = None
    memory_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    duplicate_of_event_id: str | None = None
    events_emitted: int = Field(ge=0)


# -- feedback / learning write ---------------------------------------------------


class SignalWire(BaseModel):
    """The interpreted signal learnt from one feedback record."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    source: str
    topic: str | None = None
    strength: float = Field(ge=0.0, le=1.0)
    correlation_id: str | None = Field(default=None, max_length=256)
    preference_domain: str | None = None
    preference_name: str | None = None


class FeedbackResultWire(BaseModel):
    """Stored feedback + signal, traceable to its memory."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    stored_at: UtcDateTime
    memory_id: str
    signal: SignalWire


# -- people ------------------------------------------------------------------------


class PreferenceWire(BaseModel):
    """A single user preference, traceable to a memory."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str
    domain: str | None = None
    name: str
    value: str
    confidence: Confidence
    importance: Importance


class PreferencesResult(BaseModel):
    """All preferences of one user, bucketed by domain."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    domains: list[str] = Field(default_factory=list)
    preferences: list[PreferenceWire] = Field(default_factory=list)


class DeveloperPreferencesResult(BaseModel):
    """Developer-workflow preferences, bucketed by domain."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    languages: list[PreferenceWire] = Field(default_factory=list)
    coding_style: list[PreferenceWire] = Field(default_factory=list)
    testing: list[PreferenceWire] = Field(default_factory=list)
    explanation_detail: list[PreferenceWire] = Field(default_factory=list)
    commit_style: list[PreferenceWire] = Field(default_factory=list)
    deployment: list[PreferenceWire] = Field(default_factory=list)


class PersonRowWire(BaseModel):
    """A lightweight row for a known person."""

    model_config = ConfigDict(extra="forbid")

    person_id: str
    name: str | None = None
    mention_count: int = Field(ge=0)


class PeopleSummaryResult(BaseModel):
    """People known to the user, ranked by mention frequency."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    people: list[PersonRowWire] = Field(default_factory=list)


class PersonTimelineSourceWire(BaseModel):
    """Provenance for one person timeline entry."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    component: str | None = None
    version: str | None = None
    source_event_id: str | None = None
    correlation_id: str | None = Field(default=None, max_length=256)
    source_event_id_truncated: bool = False
    correlation_id_truncated: bool = False
    related_event_ids: list[str] = Field(default_factory=list, max_length=32)
    evidence: dict[str, Any] = Field(default_factory=dict, max_length=16)


class PersonTimelineEntryWire(BaseModel):
    """One dated person memory with explicit durability and provenance."""

    model_config = ConfigDict(extra="forbid")

    person_id: str
    memory_id: str
    memory_type: str
    status: str
    statement: str = Field(min_length=1, max_length=2000)
    statement_truncated: bool = False
    occurred_at: UtcDateTime
    created_at: UtcDateTime
    valid_until: UtcDateTime | None = None
    durability: str
    confidence: Confidence
    importance: Importance
    provenance: PersonTimelineSourceWire


class PersonResolutionWire(BaseModel):
    """Outcome of resolving one person name for one user.

    ``person_id`` is present exactly when the name is not ambiguous. An
    ambiguous result lists the competing ids in ``candidates`` and never merges
    them; ``created`` is true only when a new identity memory was written.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    name: str = Field(min_length=1, max_length=200)
    person_id: str | None = None
    aliases: list[str] = Field(default_factory=list, max_length=8)
    created: bool = False
    ambiguous: bool = False
    candidates: list[str] = Field(default_factory=list, max_length=8)
    memory_id: str | None = None


class PeopleTimelineResult(BaseModel):
    """Bounded historical timeline for one user-owned person."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    person_id: str
    entries: list[PersonTimelineEntryWire] = Field(
        default_factory=list,
        max_length=200,
    )
    total_entries: int = Field(ge=0)
    truncated: bool = False
    scan_truncated: bool = False
    person_known: bool = False


# -- understanding / context --------------------------------------------------------


class UnderstandResultWire(BaseModel):
    """Validated interpretation of a corpus (mirror of ``UnderstandingResult``)."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    provider: str = "unknown"
    fallback_used: bool = False
    user_id: str | None = None
    corpus_id: str | None = None
    intent: str
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: Confidence
    summary: str = Field(min_length=1, max_length=2000)
    relevant_code_concepts: list[str] = Field(default_factory=list)


class ContextResultWire(BaseModel):
    """Bounded summary of one assembled Context (never a full dump)."""

    model_config = ConfigDict(extra="forbid")

    context_id: str
    user_id: UserId
    status: str
    repository: str | None = None
    current_file: str | None = None
    current_task: str | None = None
    relevant_memory_count: int = Field(ge=0)
    previous_bug_finding_count: int = Field(ge=0)
    previous_decision_count: int = Field(ge=0)
    developer_preference_count: int = Field(ge=0)
    relevant_people_count: int = Field(ge=0)
    fallback_used: bool = False


# -- reasoning (Developer Mode) -----------------------------------------------------


class IntentWire(BaseModel):
    """What is being requested/happening (mirror of ``IntentUnderstanding``)."""

    model_config = ConfigDict(extra="forbid")

    intent_kind: str
    confidence: Confidence
    keywords: list[str] = Field(default_factory=list)
    repository: str | None = None
    target_file: str | None = None
    target_line: int | None = Field(default=None, ge=1)
    fallback_used: bool = False
    query: str = Field(default="", max_length=4096)


class BugFindingWire(BaseModel):
    """A potential bug (never a certainty claim)."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    repository: str
    file: str
    line: int = Field(ge=1)
    column: int | None = Field(default=None, ge=1)
    title: str
    message: str
    severity: str
    confidence: Confidence
    check: str
    suggested_fix: str | None = None


class ReviewFindingWire(BaseModel):
    """A lightweight code-review finding with an explicit category."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    repository: str
    file: str
    line: int = Field(ge=1)
    category: str
    severity: str
    explanation: str
    confidence: Confidence
    suggestion: str | None = None


class TestOutcomeWire(BaseModel):
    """Core Brain's summary of supplied test results (never fabricated)."""

    model_config = ConfigDict(extra="forbid")

    provided: bool
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(ge=0)
    summary: str = ""
    reason: str | None = None


class ReasoningWire(BaseModel):
    """Everything determined about one developer context (bounded view)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    repository: str
    created_at: UtcDateTime
    intent: IntentWire
    bugs: list[BugFindingWire] = Field(default_factory=list)
    review_findings: list[ReviewFindingWire] = Field(default_factory=list)
    tests: TestOutcomeWire
    files_scanned: int = Field(ge=0)
    total_changed: int = Field(ge=0)
    context_used: bool = False
    learning_used: bool = False


class PlanWire(BaseModel):
    """Pure-data proposals; the client/product executes nothing."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    decision: BrainDecision
    proposed_actions: list[ProposedAction] = Field(default_factory=list)


class AnalyzeDeveloperResult(BaseModel):
    """The full Developer Mode result: reasoning + plan + emitted events."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    correlation_id: str
    reasoning: ReasoningWire
    plan: PlanWire
    events: list[BrainEvent] = Field(default_factory=list)


# -- learning reads -----------------------------------------------------------------


class TopicAffinityWire(BaseModel):
    """Bounded belief about a topic from accepted/rejected/outcome signals."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    positive: int = Field(ge=0)
    negative: int = Field(ge=0)
    ignored: int = Field(ge=0)
    positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    direction: str = "unknown"


class PreferenceEvidenceWire(BaseModel):
    """Belief weight for a learned developer preference."""

    model_config = ConfigDict(extra="forbid")

    key: str
    domain: str | None = None
    name: str
    positive: int = Field(ge=0)
    negative: int = Field(ge=0)
    weight: float = Field(ge=0.0, le=1.0)
    positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class LearningStatusResult(BaseModel):
    """The current aggregated learning state of one user."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    signal_counts: dict[str, int] = Field(default_factory=dict)
    topics: list[TopicAffinityWire] = Field(default_factory=list)
    preference_evidence: list[PreferenceEvidenceWire] = Field(default_factory=list)


class NudgeWire(BaseModel):
    """A single deterministic advisory hint for a client to display."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    direction: str
    strength: float = Field(ge=0.0, le=1.0)
    suggestion: str


class AssistanceProfileResult(BaseModel):
    """Personalization view consumed by clients (explicit rules only)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    explanation_detail: PreferenceWire | None = None
    top_affinities: list[TopicAffinityWire] = Field(default_factory=list)
    avoid_topics: list[TopicAffinityWire] = Field(default_factory=list)
    nudges: list[NudgeWire] = Field(default_factory=list)
    feedback_count: int = Field(ge=0)
    preference_count: int = Field(ge=0)
    source_memory_ids: list[str] = Field(default_factory=list)
    generated_at: UtcDateTime


class FeedbackHistoryItemWire(BaseModel):
    """One stored feedback + the signal learnt from it."""

    model_config = ConfigDict(extra="forbid")

    stored_at: UtcDateTime
    memory_id: str
    kind: str
    source: str
    topic: str | None = None
    strength: float = Field(ge=0.0, le=1.0)
    correlation_id: str | None = None
    note: str | None = None


class FeedbackHistoryResult(BaseModel):
    """Recent feedback history of one user (newest first)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    items: list[FeedbackHistoryItemWire] = Field(default_factory=list)