"""Developer Mode pipeline (Phase 6) — one end-to-end call.

Follows the spec event flow: reason (intent + bug detection + review + test
interpretation) → plan (pure-data proposals) → emit Brain Events (bug_detected
→ fix_proposed → test_result → review_finding → deploy_proposed). Everything is
deterministic and shares one correlation id. Nothing is executed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.brain_events.events import BrainEvent
from contracts.common.ids import UserId
from contracts.decisions.decisions import ActionType
from core.understanding.developer import DeveloperContext

from ..actions.models import ActionPlan
from ..actions.planner import ActionPlanner
from ..reasoning.models import ReasoningResult
from ..reasoning.reasoning import ReasoningEngine
from .emitter import BrainEventEmitter


class DevOutcome(BaseModel):
    """Result of one Developer Mode pipeline run (events + reasoning + plan)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    correlation_id: str
    reasoning: ReasoningResult
    plan: ActionPlan
    events: list[BrainEvent] = Field(default_factory=list)


class DevModePipeline:
    """One call, the whole developer-mode demo flow."""

    def __init__(
        self,
        *,
        reasoning: ReasoningEngine | None = None,
        planner: ActionPlanner | None = None,
        emitter: BrainEventEmitter | None = None,
    ) -> None:
        self._reasoning = reasoning or ReasoningEngine()
        self._planner = planner or ActionPlanner()
        self._emitter = emitter or BrainEventEmitter()

    def run(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
        ask_deploy: bool = False,
        correlation_id: str | None = None,
    ) -> DevOutcome:
        if not isinstance(context, DeveloperContext):
            from ..reasoning.exceptions import ReasoningValidationError

            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        reasoning = self._reasoning.reason(context, task=task)
        plan = self._planner.plan(
            context,
            reasoning,
            correlation_id=correlation_id,
            ask_deploy=ask_deploy,
        )
        correlation = plan.correlation_id

        events: list[BrainEvent] = []
        for finding in reasoning.bugs:
            events.append(
                self._emitter.bug_detected(finding, correlation_id=correlation)
            )
        for action in plan.proposed_actions:
            if action.action_type == ActionType.CODE_FIX:
                events.append(
                    self._emitter.fix_proposed(action, correlation_id=correlation)
                )
        if reasoning.tests.provided:
            events.append(
                self._emitter.test_result(
                    reasoning.tests, correlation_id=correlation
                )
            )
        for finding in reasoning.review_findings:
            events.append(
                self._emitter.review_finding(finding, correlation_id=correlation)
            )
        for action in plan.proposed_actions:
            if action.action_type == ActionType.DEPLOY:
                events.append(
                    self._emitter.deploy_proposed(action, correlation_id=correlation)
                )

        return DevOutcome(
            user_id=reasoning.user_id,
            correlation_id=correlation,
            reasoning=reasoning,
            plan=plan,
            events=events,
        )