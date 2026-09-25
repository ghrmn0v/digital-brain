"""Feedback interpreter (Phase 7) — deterministic Feedback → LearningSignal.

Turns a ``contracts.feedback.Feedback`` record into a learning signal WITHOUT
machine learning. All rules are explicit and honest:

- the signal kind comes from the label / outcome / reward value the Product
  layer supplied (or an explicit ``metadata["signal"]`` override);
- strength is derived from the numeric value when present;
- the topic is taken from metadata, never invented by an LLM;
- preference hints are extracted predictably and stay nullable when unknown.

``record_feedback`` may NEVER invent a signal: an unreadable record raises
:class:`LearningValidationError`.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from contracts.feedback.feedback import Feedback, FeedbackKind

from core.people.models import PreferenceDomain

from .exceptions import LearningValidationError
from .models import LearningSignal, SignalKind, _NEGATIVE_KINDS, _POSITIVE_KINDS

_LABELS: dict[str, SignalKind] = {
    "accepted": SignalKind.ACCEPTED,
    "accept": SignalKind.ACCEPTED,
    "approved": SignalKind.ACCEPTED,
    "rejected": SignalKind.REJECTED,
    "reject": SignalKind.REJECTED,
    "denied": SignalKind.REJECTED,
    "ignored": SignalKind.IGNORED,
    "ignore": SignalKind.IGNORED,
    "skipped": SignalKind.IGNORED,
    "corrected": SignalKind.CORRECTED,
    "successful": SignalKind.SUCCESSFUL,
    "success": SignalKind.SUCCESSFUL,
    "passed": SignalKind.SUCCESSFUL,
    "unsuccessful": SignalKind.UNSUCCESSFUL,
    "failed": SignalKind.UNSUCCESSFUL,
    "failure": SignalKind.UNSUCCESSFUL,
}

_BASE_STRENGTH: dict[SignalKind, float] = {
    SignalKind.ACCEPTED: 0.8,
    SignalKind.CORRECTED: 0.7,
    SignalKind.SUCCESSFUL: 0.7,
    SignalKind.REJECTED: 0.8,
    SignalKind.UNSUCCESSFUL: 0.8,
    SignalKind.IGNORED: 0.2,
}

_GREEN_TOKENS = frozenset(
    {"green", "passed", "pass", "clean", "ok", "success", "0 failures"}
)
_RED_TOKENS = frozenset({"red", "failed", "fail", "broken"})


class FeedbackInterpreter:
    """Deterministic conversion of a Feedback contract into a signal."""

    def interpret(self, feedback: Feedback) -> LearningSignal:
        self._validate(feedback)
        kind = self._resolve_kind(feedback)
        strength = self._strength(feedback, kind)
        metadata = feedback.metadata or {}

        topic = self._topic(metadata)
        domain, name, value = self._preference_hint(topic, metadata)

        return LearningSignal(
            signal_id=f"sig_{uuid4().hex[:16]}",
            user_id=feedback.user_id,
            kind=kind,
            source=feedback.source,
            topic=topic,
            strength=strength,
            delta_importance=self._delta_importance(kind, strength),
            correlation_id=feedback.correlation_id,
            target_type=self._target_type(feedback),
            target_id=self._target_id(feedback),
            tests_were_green=self._tests_status(metadata),
            preference_domain=domain,
            preference_name=name,
            preference_value=value,
            note=feedback.note,
            created_at=feedback.created_at,
        )

    # -- kind resolution -----------------------------------------------------
    @staticmethod
    def _validate(feedback: Feedback) -> None:
        if not feedback.user_id or not str(feedback.user_id).strip():
            raise LearningValidationError("user_id must be a non-empty string")

    def _resolve_kind(self, feedback: Feedback) -> SignalKind:
        metadata = feedback.metadata or {}

        override = metadata.get("signal")
        if isinstance(override, str):
            kind = _LABELS.get(override.strip().lower())
            if kind is not None:
                return kind

        label = (feedback.label or "").strip().lower()
        if label in _LABELS:
            return _LABELS[label]

        if feedback.kind in (FeedbackKind.OUTCOME, FeedbackKind.REWARD):
            if label in ("successful", "unsuccessful"):
                return _LABELS[label]
            if feedback.value is None:
                raise LearningValidationError(
                    "outcome/reward feedback needs a value or a label"
                )
            if feedback.value > 0:
                return SignalKind.SUCCESSFUL
            if feedback.value < 0:
                return SignalKind.UNSUCCESSFUL
            return SignalKind.IGNORED

        if feedback.value is not None:
            if feedback.value > 0:
                return SignalKind.ACCEPTED
            if feedback.value < 0:
                return SignalKind.REJECTED
            return SignalKind.IGNORED

        raise LearningValidationError(
            "cannot interpret feedback: no signal, label or value"
        )

    # -- derived fields ------------------------------------------------------
    @staticmethod
    def _strength(feedback: Feedback, kind: SignalKind) -> float:
        base = _BASE_STRENGTH[kind]
        if feedback.value is not None:
            scaled = base * abs(feedback.value)
            return round(min(1.0, scaled), 3)
        return base

    @staticmethod
    def _delta_importance(kind: SignalKind, strength: float) -> float:
        if kind == SignalKind.IGNORED:
            return 0.0
        step = 0.06 if kind in _NEGATIVE_KINDS else 0.05
        delta = step * strength
        return round(-delta if kind in _NEGATIVE_KINDS else delta, 5)

    @staticmethod
    def _topic(metadata: dict[str, Any]) -> str | None:
        raw = metadata.get("topic")
        topic = str(raw).strip() if raw is not None else ""
        if topic:
            return topic
        action = metadata.get("action_type")
        if isinstance(action, str) and action.strip():
            return f"suggestion:{str(action).strip()}"
        return None

    @staticmethod
    def _preference_hint(
        topic: str | None, metadata: dict[str, Any]
    ) -> tuple[PreferenceDomain | None, str | None, str | None]:
        explicit = metadata.get("preference_domain")
        if isinstance(explicit, str):
            for domain in PreferenceDomain:
                if explicit == domain.value:
                    name = metadata.get("preference_name", "preference")
                    value = metadata.get("preference_value")
                    if isinstance(name, str) and name.strip():
                        return (
                            domain,
                            name.strip(),
                            str(value).strip() if value is not None else None,
                        )
        if topic:
            lowered = topic.lower()
            if any(word in lowered for word in
                   ("concise", "explanation", "verbose", "bullets", "detail")):
                return (PreferenceDomain.EXPLANATION_DETAIL, "explanation", topic)
            if any(word in lowered for word in
                   ("test", "tests", "pytest", "coverage", "testing")):
                return (PreferenceDomain.TESTING, "testing-behavior", topic)
            if any(word in lowered for word in
                   ("commit", "commit-style", "conventional")):
                return (PreferenceDomain.COMMIT_STYLE, "commit-style", topic)
            if any(word in lowered for word in
                   ("deploy", "deployment", "rollout", "release")):
                return (PreferenceDomain.DEPLOYMENT, "deployment-behavior", topic)
        return (None, None, None)

    @staticmethod
    def _tests_status(metadata: dict[str, Any]) -> bool | None:
        raw = metadata.get("tests_status") or metadata.get("tests_state")
        if raw is None:
            raw = metadata.get("tests")
        if not isinstance(raw, str):
            return None
        lowered = raw.strip().lower()
        if lowered in _GREEN_TOKENS or "passed" in lowered:
            return True
        if lowered in _RED_TOKENS or ("failed" in lowered and "0 failures" not in lowered):
            return False
        return None

    @staticmethod
    def _target_type(feedback: Feedback) -> str | None:
        target = feedback.target
        if target.decision_id:
            return "decision"
        if target.action_id:
            return "action"
        if target.event_id:
            return "event"
        if target.memory_id:
            return "memory"
        return None

    @staticmethod
    def _target_id(feedback: Feedback) -> str | None:
        target = feedback.target
        return (
            target.decision_id
            or target.action_id
            or target.event_id
            or target.memory_id
        )