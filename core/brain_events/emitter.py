"""BrainEventEmitter (Phase 6).

Builds validated ``contracts.brain_events.BrainEvent`` records (pure data) for
the Developer Mode pipeline. The emitter never executes anything — it only
serializes reasoning/proposals into events Fly and Product can consume.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contracts.brain_events.events import BrainEvent, BrainEventType
from contracts.common.types import Source
from contracts.decisions.decisions import ActionType, ProposedAction

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

    def _event(self, etype, user_id, payload, related_ids) -> BrainEvent:
        return BrainEvent(
            id=self._event_id(),
            type=etype,
            timestamp=self._now(),
            user_id=user_id,
            source=self._source,
            related_ids=list(related_ids),
            payload=payload,
        )

    def bug_detected(
        self, finding: BugFinding, *, correlation_id: str
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
        )

    def fix_proposed(
        self, action: ProposedAction, *, correlation_id: str
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
        )

    def test_result(
        self, interpretation: TestResultInterpretation, *, correlation_id: str
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
        )

    def review_finding(
        self, finding: ReviewFinding, *, correlation_id: str
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
        )

    def deploy_proposed(
        self, action: ProposedAction, *, correlation_id: str
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
        )