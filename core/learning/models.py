"""Learning + personalization output models (Phase 7).

Everything here is derived, deterministic and platform-independent. The Brain
owns the *learning* layer; the Product/Fly layers consume these structured
views. No fake machine learning — signals are honest event counts and bounded
belief weights computed from the Feedback contract.

Storage split follows the existing architecture:

- raw ``Feedback`` records are persisted as ``OBSERVATION`` memories (durable
  trace, retrievable by future reasoning);
- aggregated learning state lives in a ``LearningStateRepository``;
- learned *preferences* are recorded through the existing preference engine
  (People Intelligence) so Context + Reasoning already see them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import EventId, MemoryId, UserId
from contracts.feedback.feedback import Feedback, FeedbackSource
from contracts.people.person import PersonId  # noqa: F401 (stable identity anchor)

from core.people.models import Preference, PreferenceDomain


class SignalKind(str, Enum):
    """The deterministic signal a feedback record encodes (additive)."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IGNORED = "ignored"
    CORRECTED = "corrected"
    SUCCESSFUL = "successful"
    UNSUCCESSFUL = "unsuccessful"


_POSITIVE_KINDS = frozenset(
    {SignalKind.ACCEPTED, SignalKind.CORRECTED, SignalKind.SUCCESSFUL}
)
_NEGATIVE_KINDS = frozenset(
    {SignalKind.REJECTED, SignalKind.UNSUCCESSFUL}
)


class LearningSignal(BaseModel):
    """One interpreted feedback signal, ready to be learned from."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str
    user_id: UserId
    kind: SignalKind
    source: FeedbackSource
    topic: str | None = None
    strength: float = Field(ge=0.0, le=1.0)
    delta_importance: float = Field(ge=-1.0, le=1.0)
    correlation_id: str | None = Field(default=None, max_length=256)
    target_type: str | None = Field(default=None, max_length=32)
    target_id: str | None = None
    tests_were_green: bool | None = None
    preference_domain: PreferenceDomain | None = None
    preference_name: str | None = None
    preference_value: str | None = None
    note: str | None = Field(default=None, max_length=1024)
    created_at: datetime


class StoredFeedback(BaseModel):
    """A feedback + the signal learnt from it, traceable to its memory."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    feedback: Feedback
    signal: LearningSignal
    memory_id: MemoryId
    stored_at: datetime


class TopicAffinity(BaseModel):
    """Bounded belief about a topic from accepted/rejected/outcome signals."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    positive: int = 0
    negative: int = 0
    ignored: int = 0
    delta_importance: float = 0.0
    updated_at: datetime

    @property
    def sample_size(self) -> int:
        return self.positive + self.negative

    @property
    def positive_rate(self) -> float | None:
        total = self.sample_size
        if total == 0:
            return None
        return round(self.positive / total, 3)

    @property
    def direction(self) -> str:
        """'positive' | 'negative' | 'neutral' | 'unknown' (deterministic)."""
        total = self.sample_size
        if total == 0:
            return "unknown"
        rate = self.positive / total
        if rate >= 0.6:
            return "positive"
        if rate <= 0.25:
            return "negative"
        return "neutral"


class PreferenceEvidence(BaseModel):
    """Belief weight for a learned developer preference."""

    model_config = ConfigDict(extra="forbid")

    key: str
    domain: PreferenceDomain | None
    name: str
    positive: int = 0
    negative: int = 0
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    updated_at: datetime

    @property
    def positive_rate(self) -> float | None:
        total = self.positive + self.negative
        if total == 0:
            return None
        return round(self.positive / total, 3)


class LearningStatus(BaseModel):
    """The current aggregated learning state of one user (bounded)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    signal_counts: dict[str, int] = Field(default_factory=dict)
    topics: list[TopicAffinity] = Field(default_factory=list)
    preference_evidence: list[PreferenceEvidence] = Field(default_factory=list)
    updated_at: datetime | None = None

    def affinity(self, topic: str) -> TopicAffinity | None:
        for affinity in self.topics:
            if affinity.topic == topic:
                return affinity
        return None

    def evidence(self, key: str) -> PreferenceEvidence | None:
        for evidence in self.preference_evidence:
            if evidence.key == key:
                return evidence
        return None


class AssistanceNudge(BaseModel):
    """A single deterministic advisory hint for Product/Fly to display."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    direction: str
    strength: float = Field(ge=0.0, le=1.0)
    suggestion: str


class AssistanceProfile(BaseModel):
    """Personalization view consumed by future reasoning and clients."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    explanation_detail: Preference | None = None
    top_affinities: list[TopicAffinity] = Field(default_factory=list)
    avoid_topics: list[TopicAffinity] = Field(default_factory=list)
    nudges: list[AssistanceNudge] = Field(default_factory=list)
    feedback_count: int = 0
    preference_count: int = 0
    source_memory_ids: list[MemoryId] = Field(default_factory=list)
    generated_at: datetime


@dataclass(frozen=True)
class LearningLimits:
    """Resource budget that keeps learning deterministic and small."""

    max_state_topics: int = 50
    max_state_preference_evidence: int = 20
    max_profile_affinities: int = 5
    max_feedback_history: int = 50
    min_evidence_for_preference: int = 2
    min_evidence_for_avoidance: int = 2
    reject_rate_threshold: float = 0.25
    accept_rate_threshold: float = 0.6
    importance_step: float = 0.05
    importance_max: float = 0.95
    importance_min: float = 0.1
    feedback_scan_limit: int = 1000