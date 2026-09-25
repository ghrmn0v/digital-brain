"""BrainEventEmitter (Phase 6 + Phase 8 Slice 1).

Builds validated ``contracts.brain_events.BrainEvent`` records (pure data) for
the Developer Mode pipeline and for the Brain-owned state transitions exposed
through the event infrastructure (memory.created, preference.updated,
learning.signal.detected, decision.created, action.proposed). The emitter
never executes anything — it only serializes Brain state/reasoning/proposals
into events consumers (Fly, Product, mobile, future connectors) can use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contracts.brain_events.events import BrainEvent, BrainEventType
from contracts.common.types import Source
from contracts.decisions.decisions import (
    ActionType,
    BrainDecision,
    ProposedAction,
)
from contracts.memory.memory import Memory

from core.learning.models import LearningSignal
from core.people.models import Preference

from ..reasoning.models import BugFinding, ReviewFinding, TestResultInterpretation

_DEFAULT_SOURCE = Source(provider="core", component="brain-events")


class BrainEventEmitter:
    """Deterministic builder of typed Brain Events."""

    def __init__(
        self,
        *,
        source: Source | None = None,
        now=None,
    ) -> None:
        self._source = source or _DEFAULT_SOURCE
        self._now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _event_id() -> str:
        return f"evt_{uuid4().hex[:16]}"

    def _event(
        self,
        etype,
        user_id,
        payload,
        related_ids,
        source: Source | None = None,
    ) -> BrainEvent:
        return BrainEvent(
            id=self._event_id(),
            type=etype,
            timestamp=self._now(),
            user_id=user_id,
            source=source if source is not None else self._source,
            related_ids=list(related_ids),
            payload=payload,
        )

    def bug_detected(
        self,
        finding: BugFinding,
        *,
        correlation_id: str,
        source: Source | None = None,
    ) -> BrainEvent:
        return self._event(
            BrainEventType.DEVELOPER_BUG_DETECTED,
            finding.user_id,
            {
                "event_id": finding.finding_id,
                "repository": finding.repository,
                "file": finding.file,
                "line": finding.line,
                "column": finding.column,
                "title": finding.title,
                "message": finding.message,
                "severity": finding.severity.value,
                "confidence": finding.confidence,
                "correlation_id": correlation_id,
                "finding_id": finding.finding_id,
            },
            [finding.finding_id],
            source=source,
        )

    def fix_proposed(
        self,
        action: ProposedAction,
        *,
        correlation_id: str,
        source: Source | None = None,
    ) -> BrainEvent:
        params = action.parameters or {}
        return self._event(
            BrainEventType.DEVELOPER_FIX_PROPOSED,
            action.user_id,
            {
                "action_id": action.action_id,
                "affected_file": params.get("file"),
                "affected_lines": [params.get("line")] if params.get("line") else [],
                "explanation": action.reason,
                "proposed_change": params.get("proposed_change"),
                "confidence": action.confidence,
                "required_permission_level": action.requested_permission_level.value,
                "correlation_id": correlation_id,
            },
            [action.action_id],
            source=source,
        )

    def test_result(
        self,
        interpretation: TestResultInterpretation,
        *,
        correlation_id: str,
        source: Source | None = None,
    ) -> BrainEvent:
        return self._event(
            BrainEventType.DEVELOPER_TEST_RESULT,
            interpretation.user_id,
            {
                "passed": interpretation.passed,
                "failed": interpretation.failed,
                "skipped": interpretation.skipped,
                "errors": interpretation.errors,
                "summary": interpretation.summary,
                "reason": interpretation.reason,
                "confidence": interpretation.confidence,
                "correlation_id": correlation_id,
            },
            [],
            source=source,
        )

    def review_finding(
        self,
        finding: ReviewFinding,
        *,
        correlation_id: str,
        source: Source | None = None,
    ) -> BrainEvent:
        return self._event(
            BrainEventType.DEVELOPER_REVIEW_FINDING,
            finding.user_id,
            {
                "review_finding_id": finding.finding_id,
                "file": finding.file,
                "line": finding.line,
                "severity": finding.severity.value,
                "explanation": finding.explanation,
                "confidence": finding.confidence,
                "category": finding.category.value,
                "correlation_id": correlation_id,
            },
            [finding.finding_id],
            source=source,
        )

    def deploy_proposed(
        self,
        action: ProposedAction,
        *,
        correlation_id: str,
        source: Source | None = None,
    ) -> BrainEvent:
        params = action.parameters or {}
        tests_green = bool(action.action_type == ActionType.DEPLOY)
        return self._event(
            BrainEventType.DEVELOPER_DEPLOY_PROPOSED,
            action.user_id,
            {
                "action_id": action.action_id,
                "environment": params.get("environment"),
                "repository": params.get("repository"),
                "reason": action.reason,
                "test_status": "green" if tests_green else "unknown",
                "risk_confidence": action.confidence,
                "required_permission_level": action.requested_permission_level.value,
                "correlation_id": correlation_id,
            },
            [action.action_id],
            source=source,
        )

    # -- Brain-owned events (Phase 8 Slice 1) --------------------------------
    def memory_created(
        self,
        memory: Memory,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        """A memory was durably created by the Brain."""
        return self._event(
            BrainEventType.MEMORY_CREATED,
            memory.user_id,
            {
                "memory_id": memory.memory_id,
                "type": memory.type.value,
                "importance": memory.importance,
                "confidence": memory.confidence,
                "status": memory.status.value,
                "correlation_id": correlation_id,
            },
            [memory.memory_id],
            source=source,
        )

    def person_created(
        self,
        user_id: str,
        person_id: str,
        name: str,
        *,
        memory_id: str | None = None,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        """A person identity was resolved and recorded for the first time."""
        payload: dict[str, Any] = {
            "person_id": person_id,
            "name": name,
            "correlation_id": correlation_id,
        }
        if memory_id is not None:
            payload["memory_id"] = memory_id
        return self._event(
            BrainEventType.PERSON_CREATED,
            user_id,
            payload,
            [memory_id] if memory_id is not None else [],
            source=source,
        )

    def preference_updated(
        self,
        user_id: str,
        preference: Preference,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        """A developer/user preference was written (or superseded)."""
        return self._event(
            BrainEventType.PREFERENCE_UPDATED,
            user_id,
            {
                "preference": preference.name,
                "value": preference.value,
                "source": (
                    preference.domain.value if preference.domain else "general"
                ),
                "domain": (
                    preference.domain.value if preference.domain else None
                ),
                "memory_id": preference.memory_id,
                "correlation_id": correlation_id,
            },
            [preference.memory_id],
            source=source,
        )

    def learning_signal_detected(
        self,
        signal: LearningSignal,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        """A feedback record produced a learning signal (state transition)."""
        resolved = (
            correlation_id if correlation_id is not None else signal.correlation_id
        )
        return self._event(
            BrainEventType.LEARNING_SIGNAL_DETECTED,
            signal.user_id,
            {
                "signal": signal.kind.value,
                "source": signal.source.value,
                "value": signal.strength,
                "topic": signal.topic,
                "delta_importance": signal.delta_importance,
                "correlation_id": resolved,
            },
            [],
            source=source,
        )

    def decision_created(
        self,
        decision: BrainDecision,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        """A BrainDecision was produced (Brain proposes — nothing executed)."""
        resolved = (
            correlation_id if correlation_id is not None else decision.correlation_id
        )
        return self._event(
            BrainEventType.DECISION_CREATED,
            decision.user_id,
            {
                "decision_id": decision.decision_id,
                "confidence": decision.confidence,
                "action_count": len(decision.proposed_actions),
                "reason": decision.reason,
                "correlation_id": resolved,
            },
            [decision.decision_id],
            source=source,
        )

    def action_proposed(
        self,
        action: ProposedAction,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        """A proposed (never executed) action was added to a decision."""
        resolved = (
            correlation_id if correlation_id is not None else action.correlation_id
        )
        return self._event(
            BrainEventType.ACTION_PROPOSED,
            action.user_id,
            {
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "requested_permission_level": action.requested_permission_level.value,
                "reason": action.reason,
                "correlation_id": resolved,
            },
            [action.action_id],
            source=source,
        )
