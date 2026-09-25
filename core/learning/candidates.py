"""LLM-suggested learning candidates -> the existing Learning Engine.

The rule this module enforces: **a model answer is never a fact.**

Gemini (or any provider) may return something that looks like a user
preference. That output is a *candidate*. The Brain decides whether it becomes
evidence, and the existing Learning Engine decides whether evidence becomes a
stored preference. Nothing here writes memory directly, and nothing here
duplicates the learning policy.

Routing rules (deliberately conservative):

============  ==========================  =========================
evidence      routed as                   effect
============  ==========================  =========================
explicit      ``record_preference``       stored immediately as an
                                          explicit user preference
repeated_*    ``record_feedback``         weak, counted evidence; becomes a
                                          preference only after the
                                          Learning Engine's threshold
inference     not recorded                a model's guess is not a
                                          user signal at all
============  ==========================  =========================

Why the split: an explicit statement ("I prefer TypeScript") is the user
speaking for themselves, so the Brain's own explicit path
(``PeopleIntelligence.record_preference``) is the honest route — it stores the
value with its provenance. Repeated patterns are behaviour, not statements, so
they go through the Learning Engine as counted evidence and only become a
preference once the existing threshold is met.

Explicit-over-learned precedence is not re-implemented here: an explicit
preference owns its conflict key, and the Learning Engine's
``_has_explicit_preference`` policy then blocks any learned write for the same
``<domain>:<name>``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import UserId
from contracts.common.types import Source
from core.people.models import PreferenceDomain
from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)


class LearningCandidateKind(str, Enum):
    """What the model believes it observed."""

    PREFERENCE = "preference"
    AVOID_TOPIC = "avoid_topic"
    FACT = "fact"


class LearningEvidence(str, Enum):
    """How strong the signal behind a candidate is."""

    EXPLICIT_STATEMENT = "explicit_user_statement"
    REPEATED_ACCEPTANCE = "repeated_acceptance"
    REPEATED_REJECTION = "repeated_rejection"
    INFERENCE = "inference"


_EXPLICIT_EVIDENCE = {LearningEvidence.EXPLICIT_STATEMENT}
_IMPLICIT_EVIDENCE = {
    LearningEvidence.REPEATED_ACCEPTANCE,
    LearningEvidence.REPEATED_REJECTION,
}
_SIGNAL_BY_EVIDENCE = {
    # An explicit statement ("I prefer TypeScript") is itself an acceptance of
    # that preference, so it carries the same signal. The Feedback *kind*
    # (EXPLICIT vs IMPLICIT) is what keeps the evidence weight different.
    LearningEvidence.EXPLICIT_STATEMENT: "accepted",
    LearningEvidence.REPEATED_ACCEPTANCE: "accepted",
    LearningEvidence.REPEATED_REJECTION: "rejected",
}


class LearningCandidate(BaseModel):
    """A provider's suggestion about the user. Never a stored fact by itself.

    ``preference_domain`` is optional on purpose: the Brain refuses to invent a
    domain. Without a recognised domain the candidate still becomes stored
    evidence, it just cannot become a stored *preference* yet.
    """

    model_config = ConfigDict(extra="forbid")

    kind: LearningCandidateKind = LearningCandidateKind.PREFERENCE
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)
    evidence: LearningEvidence = LearningEvidence.INFERENCE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    topic: str | None = Field(default=None, max_length=120)
    preference_domain: str | None = Field(default=None, max_length=64)

    @property
    def is_recordable(self) -> bool:
        """Only evidence-backed candidates may reach the Learning Engine."""
        return self.evidence in _EXPLICIT_EVIDENCE or self.evidence in _IMPLICIT_EVIDENCE


class PersonalizedAnswer(BaseModel):
    """Structured provider output for a personalized Brain request.

    Used as the target schema of ``LLMGateway.generate_structured`` so the
    gateway validates it exactly like every other structured result. A provider
    that returns free-form prose fails validation and the Brain falls back.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    used_context: bool = False
    missing_context: list[str] = Field(default_factory=list, max_length=16)
    candidates: list[LearningCandidate] = Field(default_factory=list, max_length=16)


class RecordedCandidate(BaseModel):
    """What the Brain actually did with one candidate (audit-friendly)."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str
    evidence: LearningEvidence
    recorded: bool
    reason: str = ""
    feedback_id: str | None = None


def candidate_to_feedback(
    candidate: LearningCandidate,
    *,
    user_id: UserId,
    target_event_id: str,
    correlation_id: str | None = None,
    created_at: datetime | None = None,
) -> Feedback:
    """Convert one candidate into an existing ``Feedback`` record.

    ``target_event_id`` is required: the Brain never invents a traceability
    anchor, so a candidate can only be learned from a real interaction.

    The feedback source is ``system`` because the Brain itself is the actor
    that turned a provider suggestion into evidence — the end user did not
    send this record.
    """
    if not candidate.is_recordable:
        raise ValueError(
            "only evidence-backed candidates can become feedback; "
            f"{candidate.evidence.value!r} is not evidence"
        )
    explicit = candidate.evidence in _EXPLICIT_EVIDENCE
    metadata: dict[str, Any] = {
        "llm_candidate": True,
        "candidate_kind": candidate.kind.value,
        "candidate_confidence": candidate.confidence,
        "candidate_evidence": candidate.evidence.value,
    }
    if candidate.topic:
        metadata["topic"] = candidate.topic
    if candidate.preference_domain and candidate.kind is LearningCandidateKind.PREFERENCE:
        # The Learning Engine's preference path keys on these three fields; a
        # missing domain simply means "evidence, not a preference yet".
        metadata["preference_domain"] = candidate.preference_domain
        metadata["preference_name"] = candidate.key
        metadata["preference_value"] = candidate.value[:2000]
    metadata["signal"] = _SIGNAL_BY_EVIDENCE.get(candidate.evidence, "ignored")
    name = f"avoid:{candidate.topic}" if (
        candidate.kind is LearningCandidateKind.AVOID_TOPIC and candidate.topic
    ) else candidate.key
    return Feedback(
        feedback_id=f"fb_llm_{uuid.uuid4().hex[:16]}",
        user_id=user_id,
        source=FeedbackSource.SYSTEM,
        kind=FeedbackKind.EXPLICIT if explicit else FeedbackKind.IMPLICIT,
        target=FeedbackTarget(event_id=target_event_id),
        label=name[:128],
        note=(
            f"{candidate.kind.value}: {candidate.value}"
        )[:1024],
        created_at=created_at or datetime.now(timezone.utc),
        correlation_id=correlation_id,
        metadata=metadata,
    )


def route_candidates(
    candidates: list[LearningCandidate],
    *,
    user_id: UserId,
    target_event_id: str,
    record: Any,
    record_preference: Any | None = None,
    correlation_id: str | None = None,
    created_at: datetime | None = None,
) -> list[RecordedCandidate]:
    """Route candidates into the Brain's own learning/preference systems.

    ``record`` is the Learning Engine's ``record_feedback`` and
    ``record_preference`` is People Intelligence's explicit write path; both are
    injected, so this module cannot persist anything by itself. Candidates that
    no sink accepts are reported, never silently dropped.
    """
    results: list[RecordedCandidate] = []
    for candidate in candidates:
        if not candidate.is_recordable:
            results.append(
                RecordedCandidate(
                    key=candidate.key,
                    value=candidate.value,
                    evidence=candidate.evidence,
                    recorded=False,
                    reason="not evidence-backed; a model inference is not a user signal",
                )
            )
            continue
        explicit = candidate.evidence in _EXPLICIT_EVIDENCE
        if explicit and record_preference is not None:
            results.append(
                _write_explicit_preference(
                    candidate,
                    user_id=user_id,
                    record_preference=record_preference,
                    correlation_id=correlation_id,
                )
            )
            continue
        feedback = candidate_to_feedback(
            candidate,
            user_id=user_id,
            target_event_id=target_event_id,
            correlation_id=correlation_id,
            created_at=created_at,
        )
        try:
            stored = record(feedback)
        except Exception as exc:  # provider-independent: never break the Brain
            results.append(
                RecordedCandidate(
                    key=candidate.key,
                    value=candidate.value,
                    evidence=candidate.evidence,
                    recorded=False,
                    reason=f"learning rejected the candidate: {type(exc).__name__}",
                )
            )
            continue
        results.append(
            RecordedCandidate(
                key=candidate.key,
                value=candidate.value,
                evidence=candidate.evidence,
                recorded=True,
                reason="routed through the Learning Engine as feedback",
                feedback_id=getattr(stored, "feedback_id", feedback.feedback_id),
            )
        )
    return results


def _write_explicit_preference(
    candidate: LearningCandidate,
    *,
    user_id: UserId,
    record_preference: Any,
    correlation_id: str | None,
) -> RecordedCandidate:
    """Store an explicitly stated preference through People Intelligence."""
    domain: Any = None
    if candidate.preference_domain:
        try:
            domain = PreferenceDomain(candidate.preference_domain)
        except ValueError:
            domain = None
    try:
        preference = record_preference(
            user_id,
            name=candidate.key,
            value=candidate.value,
            domain=domain,
            source=Source(provider="brain", component="llm-candidate"),
            metadata={
                "llm_candidate": True,
                "candidate_evidence": candidate.evidence.value,
                "candidate_confidence": candidate.confidence,
            },
        )
    except Exception as exc:
        return RecordedCandidate(
            key=candidate.key,
            value=candidate.value,
            evidence=candidate.evidence,
            recorded=False,
            reason=f"preference write rejected: {type(exc).__name__}",
        )
    return RecordedCandidate(
        key=candidate.key,
        value=candidate.value,
        evidence=candidate.evidence,
        recorded=True,
        reason="stored as an explicit user preference",
        feedback_id=getattr(preference, "memory_id", None),
    )


def answer_instruction() -> str:
    """The task instruction handed to the provider."""
    return (
        "Answer the current request using the user context provided.\n"
        "- If the context contains the answer, use it and set used_context=true.\n"
        "- Never state a user fact that is not in the context.\n"
        "- List anything you needed but did not find in missing_context.\n"
        "- Propose at most 3 candidates. A candidate must be supported by the "
        "request text itself: use evidence 'explicit_user_statement' only when "
        "the user stated it directly, 'repeated_acceptance' or "
        "'repeated_rejection' when the request shows an established pattern, and "
        "'inference' when you are only guessing.\n"
        "- For a preference candidate, set preference_domain to one of: "
        "language, testing, coding_style, commit_style, explanation_detail, "
        "deployment. Leave it empty if you are unsure; a candidate without a "
        "domain is still remembered as evidence."
    )
