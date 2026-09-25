"""BrainEventDispatcher (Phase 8 Slice 1).

Wires an :class:`~core.brain_events.emitter.BrainEventEmitter` (pure event
builder) to an :class:`~core.brain_events.sink.EventSink` (transport-independent
destination). The BrainService uses this dispatcher to turn real state
transitions (memory created, preference written, learning signal, decision and
its action proposals) into emitted events — always with user_id + correlation
propagated, always deterministic, never executed.
"""

from __future__ import annotations

from contracts.brain_events.events import BrainEvent
from contracts.decisions.decisions import BrainDecision, ProposedAction
from contracts.memory.memory import Memory
from contracts.common.types import Source

from core.learning.models import LearningSignal
from core.people.models import Preference

from ..actions.models import ActionPlan
from .emitter import BrainEventEmitter
from .sink import EventSink, NullEventSink


def _source_kwargs(source: Source | None) -> dict[str, Source]:
    return {"source": source} if source is not None else {}


class BrainEventDispatcher:
    """Emits structured Brain events through an EventSink."""

    def __init__(
        self,
        emitter: BrainEventEmitter | None = None,
        sink: EventSink | None = None,
    ) -> None:
        self._emitter = emitter or BrainEventEmitter()
        self._sink = sink if sink is not None else NullEventSink()
        if not hasattr(self._sink, "emit") or not callable(self._sink.emit):
            raise TypeError("sink must implement EventSink.emit(event)")

    @property
    def sink(self) -> EventSink:
        return self._sink

    @property
    def emitter(self) -> BrainEventEmitter:
        return self._emitter

    # -- Brain-owned events ---------------------------------------------------
    def memory_created(
        self,
        memory: Memory,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        event = self._emitter.memory_created(
            memory, correlation_id=correlation_id, **_source_kwargs(source)
        )
        self._sink.emit(event)
        return event

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
        event = self._emitter.person_created(
            user_id,
            person_id,
            name,
            memory_id=memory_id,
            correlation_id=correlation_id,
            **_source_kwargs(source),
        )
        self._sink.emit(event)
        return event

    def preference_updated(
        self,
        user_id: str,
        preference: Preference,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        event = self._emitter.preference_updated(
            user_id,
            preference,
            correlation_id=correlation_id,
            **_source_kwargs(source),
        )
        self._sink.emit(event)
        return event

    def learning_signal_detected(
        self,
        signal: LearningSignal,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        event = self._emitter.learning_signal_detected(
            signal, correlation_id=correlation_id, **_source_kwargs(source)
        )
        self._sink.emit(event)
        return event

    def decision_created(
        self,
        decision: BrainDecision,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        event = self._emitter.decision_created(
            decision, correlation_id=correlation_id, **_source_kwargs(source)
        )
        self._sink.emit(event)
        return event

    def action_proposed(
        self,
        action: ProposedAction,
        *,
        correlation_id: str | None = None,
        source: Source | None = None,
    ) -> BrainEvent:
        event = self._emitter.action_proposed(
            action, correlation_id=correlation_id, **_source_kwargs(source)
        )
        self._sink.emit(event)
        return event

    # -- plan-level ------------------------------------------------------------
    def emit_plan(
        self, plan: ActionPlan, *, source: Source | None = None
    ) -> tuple[BrainEvent, list[BrainEvent]]:
        """Emit decision.created + one action.proposed per proposal.

        A produced plan is a real Brain transition (decision created with its
        action proposals); nothing is executed. Returns
        ``(decision_event, [action_event, ...])``.
        """
        decision_event = self.decision_created(
            plan.decision,
            correlation_id=plan.correlation_id,
            **_source_kwargs(source),
        )
        action_events = [
            self.action_proposed(
                action,
                correlation_id=plan.correlation_id,
                **_source_kwargs(source),
            )
            for action in plan.proposed_actions
        ]
        return decision_event, action_events