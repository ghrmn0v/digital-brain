"""ActionPlanner (Phase 6).

Turns a ReasoningResult into PURE-DATA action proposals using the existing
``ProposedAction`` / ``BrainDecision`` contracts. The Brain proposes; it never
executes. Every proposal carries a requested (not granted) permission level and
is traceable to the reasoning finding that produced it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contracts.decisions.decisions import (
    ActionType,
    BrainDecision,
    PermissionLevel,
    ProposedAction,
)
from core.understanding.developer import DeveloperContext

from .exceptions import ActionPlanningError, ActionValidationError
from .models import ActionPlan
from ..reasoning.models import ReasoningResult, Severity


def _correlation_id() -> str:
    return f"corr_{uuid4().hex[:16]}"


class ActionPlanner:
    """Deterministic proposal builder (never executes anything)."""

    def __init__(
        self,
        *,
        min_fix_confidence: float = 0.3,
        max_proposals: int = 5,
        default_environment: str = "staging",
        now=None,
    ) -> None:
        if not 0.0 <= min_fix_confidence <= 1.0:
            raise ActionValidationError("min_fix_confidence must be in [0, 1]")
        if max_proposals < 1:
            raise ActionValidationError("max_proposals must be >= 1")
        self._min_fix_confidence = min_fix_confidence
        self._max_proposals = max_proposals
        self._default_environment = default_environment
        self._now = now or (lambda: datetime.now(timezone.utc))

    def plan(
        self,
        context: DeveloperContext,
        reasoning: ReasoningResult,
        *,
        correlation_id: str | None = None,
        ask_deploy: bool = False,
    ) -> ActionPlan:
        if not isinstance(context, DeveloperContext):
            raise ActionValidationError("context must be a DeveloperContext")
        if not isinstance(reasoning, ReasoningResult):
            raise ActionValidationError("reasoning must be a ReasoningResult")
        if reasoning.user_id != context.user_id:
            raise ActionPlanningError(
                "reasoning and context belong to different users (isolation)"
            )

        correlation_id = (
            correlation_id if correlation_id is not None else _correlation_id()
        )
        proposals: list[ProposedAction] = []

        fixes = [
            finding for finding in reasoning.bugs
            if self._fix_warranted(finding)
        ]
        for finding in sorted(
            fixes, key=lambda f: (-f.confidence, f.finding_id)
        ):
            proposals.append(
                ProposedAction(
                    action_id=f"act_{uuid4().hex[:16]}",
                    user_id=reasoning.user_id,
                    action_type=ActionType.CODE_FIX,
                    reason=finding.message,
                    parameters={
                        "file": finding.file,
                        "line": finding.line,
                        "column": finding.column,
                        "finding_id": finding.finding_id,
                        "check": finding.check,
                        "title": finding.title,
                        "proposed_change": finding.suggested_fix,
                    },
                    confidence=finding.confidence,
                    requested_permission_level=PermissionLevel.EXPLICIT,
                    created_at=self._now(),
                    correlation_id=correlation_id,
                )
            )
            if len(proposals) >= self._max_proposals:
                break

        tests = reasoning.tests
        if (
            tests.provided
            and (tests.failed + tests.errors) > 0
            and len(proposals) < self._max_proposals
        ):
            proposals.append(
                ProposedAction(
                    action_id=f"act_{uuid4().hex[:16]}",
                    user_id=reasoning.user_id,
                    action_type=ActionType.RUN_TESTS,
                    reason=tests.summary,
                    parameters={"repository": reasoning.repository},
                    confidence=max(tests.confidence, 0.4),
                    requested_permission_level=PermissionLevel.READ,
                    created_at=self._now(),
                    correlation_id=correlation_id,
                )
            )

        if (
            changed := sorted(set(context.changed_files or []))
        ) and len(proposals) < self._max_proposals:
            serious = [
                f for f in reasoning.review_findings
                if f.severity in (Severity.WARNING, Severity.HIGH, Severity.CRITICAL)
            ]
            if serious:
                top_confidence = max(f.confidence for f in serious)
                proposals.append(
                    ProposedAction(
                        action_id=f"act_{uuid4().hex[:16]}",
                        user_id=reasoning.user_id,
                        action_type=ActionType.REVIEW,
                        reason=f"{len(serious)} notable findings in changed files.",
                        parameters={"files": changed},
                        confidence=round(top_confidence, 3),
                        requested_permission_level=PermissionLevel.READ,
                        created_at=self._now(),
                        correlation_id=correlation_id,
                    )
                )

        deploy_possible = (
            ask_deploy
            and tests.provided
            and tests.failed == 0
            and tests.errors == 0
            and not fixes
            and len(proposals) < self._max_proposals
        )
        if deploy_possible:
            environment = context.user_context.get("environment")
            if not isinstance(environment, str) or not environment.strip():
                environment = self._default_environment
            proposals.append(
                ProposedAction(
                    action_id=f"act_{uuid4().hex[:16]}",
                    user_id=reasoning.user_id,
                    action_type=ActionType.DEPLOY,
                    reason="Tests green and no high-warrant open findings; propose deploy.",
                    parameters={
                        "repository": reasoning.repository,
                        "environment": environment,
                    },
                    confidence=round(min(0.9, max(tests.confidence, 0.5)), 3),
                    requested_permission_level=PermissionLevel.EXPLICIT,
                    created_at=self._now(),
                    correlation_id=correlation_id,
                )
            )

        if not proposals:
            decision_reason = "No action warranted by current context."
            decision_confidence = 0.0
        else:
            counts_by_type: dict[str, int] = {}
            for proposal in proposals:
                key = proposal.action_type.value
                counts_by_type[key] = counts_by_type.get(key, 0) + 1
            counts = ", ".join(
                f"{kind}×{count}" for kind, count in counts_by_type.items()
            )
            decision_reason = f"Proposed actions: {counts}."
            decision_confidence = round(
                max(p.confidence for p in proposals), 3
            )

        decision = BrainDecision(
            decision_id=f"dec_{uuid4().hex[:16]}",
            user_id=reasoning.user_id,
            created_at=self._now(),
            reason=decision_reason,
            context_summary={
                "repository": reasoning.repository,
                "files_scanned": reasoning.files_scanned,
                "changed_files": changed,
                "intent": reasoning.intent.intent_kind.value,
                "bugs": len(reasoning.bugs),
                "review_findings": len(reasoning.review_findings),
                "tests_provided": tests.provided,
            },
            confidence=decision_confidence,
            source_event_ids=[],
            related_memory_ids=[],
            proposed_actions=proposals,
            correlation_id=correlation_id,
        )
        return ActionPlan(
            user_id=reasoning.user_id,
            correlation_id=correlation_id,
            decision=decision,
            proposed_actions=decision.proposed_actions,
            created_at=decision.created_at,
        )

    def _fix_warranted(self, finding) -> bool:
        return (
            finding.severity
            in (Severity.WARNING, Severity.HIGH, Severity.CRITICAL)
            and finding.confidence >= self._min_fix_confidence
        )