"""Developer Mode pipeline (Phase 6) — one end-to-end call.

Follows the spec event flow: reason (intent + bug detection + review + test
interpretation) → plan (pure-data proposals) → emit Brain Events (bug_detected
→ fix_proposed → test_result → review_finding → deploy_proposed). Everything is
deterministic and shares one correlation id. Nothing is executed.

Phase 8 Slice 1: an optional :class:`EventSink` may be attached. When it is,
each produced developer event is ALSO dispatched to the sink. Without a sink
the pipeline behaves exactly as before (events are only returned in the
outcome).

Phase 8 Slice 2: an optional read-only learning port is forwarded to the
ReasoningEngine, and ``run()`` accepts an optional distilled
``ReasoningContext`` (Context -> Learning Profile -> Reasoning). Without either,
behavior is unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.brain_events.events import BrainEvent
from contracts.common.ids import UserId
from contracts.decisions.decisions import ActionType
from core.understanding.developer import DeveloperContext

from ..actions.models import ActionPlan
from ..actions.planner import ActionPlanner
from ..reasoning.models import ReasoningContext, ReasoningResult
from ..reasoning.ports import LearningProfilePort
from ..reasoning.reasoning import ReasoningEngine
from .emitter import BrainEventEmitter
from .sink import EventSink


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
        sink: EventSink | None = None,
        learning: LearningProfilePort | None = None,
    ) -> None:
        self._reasoning = reasoning or ReasoningEngine(learning=learning)
        self._planner = planner or ActionPlanner()
        self._emitter = emitter or BrainEventEmitter()
        self.sink = sink
        self._learning = learning
        if reasoning is not None and learning is not None:
            reasoning.learning = learning

    @property
    def reasoning(self) -> ReasoningEngine:
        """The orchestrated ReasoningEngine (read-only access for the service)."""
        return self._reasoning

    @property
    def learning(self) -> LearningProfilePort | None:
        return self._learning

    @learning.setter
    def learning(self, value: LearningProfilePort | None) -> None:
        self._learning = value
        self._reasoning.learning = value

    def _dispatch(self, events: list[BrainEvent]) -> None:
        """Route produced developer events to the attached sink (if any)."""
        if self.sink is None:
            return
        if not hasattr(self.sink, "emit") or not callable(self.sink.emit):
            raise TypeError("sink must implement EventSink.emit(event)")
        for event in events:
            self.sink.emit(event)

    def run(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
        ask_deploy: bool = False,
        correlation_id: str | None = None,
        reasoning_context: ReasoningContext | None = None,
    ) -> DevOutcome:
        if not isinstance(context, DeveloperContext):
            from ..reasoning.exceptions import ReasoningValidationError

            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        reasoning = self._reasoning.reason(
            context, task=task, reasoning_context=reasoning_context
        )
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

        self._dispatch(events)

        return DevOutcome(
            user_id=reasoning.user_id,
            correlation_id=correlation,
            reasoning=reasoning,
            plan=plan,
            events=events,
        )