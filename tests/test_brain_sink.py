"""Tests for the Phase 8 Slice 1 event infrastructure: EventSink, the missing
Brain-owned emitters, BrainEventDispatcher, and DevModePipeline sink dispatch.

The developer.* pipeline behavior itself is unchanged and covered by the
existing test_brain_events / test_devmode_e2e suites — here we only verify the
new infrastructure is additive and correct.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contracts.brain_events.events import BrainEventType
from contracts.common.types import Source
from contracts.decisions.decisions import (
    ActionType,
    BrainDecision,
    PermissionLevel,
    ProposedAction,
)
from contracts.feedback.feedback import FeedbackSource
from contracts.memory.memory import MemoryType

from core import (
    BrainEventDispatcher,
    BrainEventEmitter,
    CollectingEventSink,
    DevModePipeline,
    NullEventSink,
)
from core.learning import LearningSignal, SignalKind
from core.memory import MemoryCandidate
from core.people import Preference, PreferenceDomain

from .memory_support import make_service
from .test_reasoning import make_context


def _memory():
    service = make_service()
    return service.create_memory(
        MemoryCandidate(
            content="Linkedin profile updated for Ana",
            user_id="usr_a",
            type=MemoryType.FACT,
            source=Source(provider="linkedin", component="test"),
        )
    )


def _preference() -> Preference:
    return Preference(
        memory_id="mem_pref_1",
        domain=PreferenceDomain.TESTING,
        name="testing",
        value="pytest",
        confidence=0.8,
        importance=0.6,
    )


def _signal() -> LearningSignal:
    return LearningSignal(
        signal_id="sig_1",
        user_id="usr_a",
        kind=SignalKind.ACCEPTED,
        source=FeedbackSource.USER,
        topic="suggestion:code.fix",
        strength=1.0,
        delta_importance=0.05,
        correlation_id="corr_sig",
        created_at=datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc),
    )


def _brain_event(
    event_type: BrainEventType = BrainEventType.DECISION_CREATED,
) -> BrainEvent:
    from contracts.brain_events.events import BrainEvent

    return BrainEvent(
        id="evt_test",
        type=event_type,
        timestamp=datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc),
        user_id="usr_a",
        source=Source(provider="core", component="test"),
        payload={},
    )


def _decision() -> BrainDecision:
    return BrainDecision(
        decision_id="dec_1",
        user_id="usr_a",
        created_at=datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc),
        reason="plan produced",
        confidence=0.5,
        correlation_id="corr_1",
    )


def _action() -> ProposedAction:
    return ProposedAction(
        action_id="act_1",
        user_id="usr_a",
        action_type=ActionType.CODE_FIX,
        reason="fix potential null reference",
        parameters={"file": "login.py", "line": 3},
        confidence=0.5,
        requested_permission_level=PermissionLevel.EXPLICIT,
        created_at=datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc),
        correlation_id="corr_1",
    )


class NullSinkTests(unittest.TestCase):
    def test_null_sink_accepts_valid_events_without_error(self):
        sink = NullEventSink()
        sink.emit(_brain_event())
        sink.emit(_brain_event(BrainEventType.ACTION_PROPOSED))

    def test_null_sink_is_runtime_checkable_port(self):
        from core.brain_events.sink import EventSink

        self.assertIsInstance(NullEventSink(), EventSink)


class CollectingSinkTests(unittest.TestCase):
    def test_captures_and_snapshots(self):
        sink = CollectingEventSink()
        sink.emit(_brain_event())
        sink.emit(_brain_event(BrainEventType.ACTION_PROPOSED))
        self.assertEqual(len(sink.emitted), 2)
        snapshot = sink.emitted
        snapshot.clear()  # mutating the snapshot must not affect the sink
        self.assertEqual(len(sink.emitted), 2)

    def test_by_user_filters(self):
        sink = CollectingEventSink()
        other = _brain_event().model_copy(update={"user_id": "usr_b"})
        sink.emit(_brain_event())
        sink.emit(other)
        self.assertEqual(len(sink.by_user("usr_a")), 1)
        self.assertEqual(len(sink.by_user("usr_b")), 1)

    def test_by_type_filters(self):
        sink = CollectingEventSink()
        sink.emit(_brain_event())
        sink.emit(_brain_event(BrainEventType.ACTION_PROPOSED))
        self.assertEqual(
            len(sink.by_type(BrainEventType.DECISION_CREATED)), 1
        )
        self.assertEqual(
            len(sink.by_type(BrainEventType.ACTION_PROPOSED)), 1
        )

    def test_clear(self):
        sink = CollectingEventSink()
        sink.emit(_brain_event())
        sink.clear()
        self.assertEqual(sink.emitted, [])


class MissingEmitterTests(unittest.TestCase):
    def setUp(self):
        self.emitter = BrainEventEmitter()

    def test_memory_created_shape_utc_owned(self):
        memory = _memory()
        event = self.emitter.memory_created(memory, correlation_id="corr_1")
        self.assertEqual(event.type, BrainEventType.MEMORY_CREATED)
        self.assertEqual(event.user_id, memory.user_id)
        self.assertIn(memory.memory_id, event.related_ids)
        payload = event.payload
        for key in ("memory_id", "type", "importance", "confidence", "status"):
            self.assertIn(key, payload)
        self.assertEqual(payload["memory_id"], memory.memory_id)
        self.assertEqual(payload["type"], "fact")
        self.assertEqual(payload["correlation_id"], "corr_1")
        self.assertEqual(event.timestamp.tzinfo, timezone.utc)

    def test_preference_updated_shape(self):
        pref = _preference()
        event = self.emitter.preference_updated(
            "usr_a", pref, correlation_id="corr_2"
        )
        self.assertEqual(event.type, BrainEventType.PREFERENCE_UPDATED)
        self.assertEqual(event.user_id, "usr_a")
        self.assertEqual(event.payload["preference"], "testing")
        self.assertEqual(event.payload["value"], "pytest")
        self.assertEqual(event.payload["source"], "testing")
        self.assertEqual(event.payload["domain"], "testing")
        self.assertEqual(event.payload["memory_id"], "mem_pref_1")
        self.assertEqual(event.payload["correlation_id"], "corr_2")

    def test_preference_updated_general_domain_source(self):
        event = self.emitter.preference_updated(
            "usr_a",
            _preference().model_copy(update={"domain": None}),
        )
        self.assertEqual(event.payload["source"], "general")
        self.assertIsNone(event.payload["domain"])

    def test_learning_signal_detected_shape_with_override(self):
        event = self.emitter.learning_signal_detected(
            _signal(), correlation_id="corr_override"
        )
        self.assertEqual(event.type, BrainEventType.LEARNING_SIGNAL_DETECTED)
        self.assertEqual(event.user_id, "usr_a")
        self.assertEqual(event.payload["signal"], "accepted")
        self.assertEqual(event.payload["source"], "user")
        self.assertEqual(event.payload["value"], 1.0)
        self.assertEqual(event.payload["correlation_id"], "corr_override")

    def test_learning_signal_uses_object_correlation_as_fallback(self):
        event = self.emitter.learning_signal_detected(_signal())
        self.assertEqual(event.payload["correlation_id"], "corr_sig")

    def test_decision_created_shape(self):
        decision = _decision()
        event = self.emitter.decision_created(decision)
        self.assertEqual(event.type, BrainEventType.DECISION_CREATED)
        self.assertEqual(event.user_id, "usr_a")
        self.assertEqual(event.payload["decision_id"], "dec_1")
        self.assertEqual(event.payload["confidence"], 0.5)
        self.assertEqual(event.payload["action_count"], 0)
        self.assertEqual(event.payload["correlation_id"], "corr_1")
        self.assertEqual(event.related_ids, ["dec_1"])

    def test_action_proposed_shape(self):
        event = self.emitter.action_proposed(_action())
        self.assertEqual(event.type, BrainEventType.ACTION_PROPOSED)
        self.assertEqual(event.user_id, "usr_a")
        self.assertEqual(event.payload["action_type"], "code.fix")
        self.assertEqual(
            event.payload["requested_permission_level"], "explicit"
        )
        self.assertEqual(event.payload["action_id"], "act_1")
        self.assertEqual(event.related_ids, ["act_1"])


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.sink = CollectingEventSink()
        self.dispatcher = BrainEventDispatcher(
            BrainEventEmitter(), self.sink
        )

    def test_memory_created_dispatches_to_sink(self):
        memory = _memory()
        event = self.dispatcher.memory_created(memory)
        self.assertEqual(self.sink.emitted, [event])

    def test_emit_plan_dispatches_decision_and_actions(self):
        plan = _plan()
        decision_event, action_events = self.dispatcher.emit_plan(plan)
        self.assertEqual(
            decision_event.type, BrainEventType.DECISION_CREATED
        )
        self.assertEqual(len(action_events), len(plan.proposed_actions))
        emitted_types = {e.type for e in self.sink.emitted}
        self.assertEqual(
            emitted_types,
            {BrainEventType.DECISION_CREATED, BrainEventType.ACTION_PROPOSED},
        )
        for event in self.sink.emitted:
            self.assertEqual(
                event.payload.get("correlation_id"), plan.correlation_id
            )
            self.assertEqual(event.user_id, plan.user_id)

    def test_dispatcher_rejects_non_sink(self):
        with self.assertRaises(TypeError):
            BrainEventDispatcher(BrainEventEmitter(), sink=object())


class PipelineSinkTests(unittest.TestCase):
    def test_pipeline_dispatches_developer_events_when_sink_attached(self):
        sink = CollectingEventSink()
        pipeline = DevModePipeline(sink=sink)
        outcome = pipeline.run(
            make_context(
                [
                    {
                        "path": "core/auth/login.py",
                        "language": "python",
                        "content": (
                            "def get_user():\n    return None\n\n"
                            "def render():\n    user = get_user()\n"
                            "    return user.email\n"
                        ),
                    }
                ],
                task="bug in login render",
                changed_files=["core/auth/login.py"],
                test_results=[
                    {"name": "login", "status": "failed",
                     "message": "boom"},
                ],
            )
        )
        self.assertEqual(sink.emitted, outcome.events)
        self.assertTrue(sink.emitted)

    def test_pipeline_without_sink_is_unchanged(self):
        pipeline = DevModePipeline()
        outcome_a = pipeline.run(
            make_context(
                [
                    {
                        "path": "a.py",
                        "language": "python",
                        "content": "def f():\n    pass\n",
                    }
                ]
            )
        )
        self.assertIsNone(pipeline.sink)
        # existing behavior: events only returned in the outcome
        self.assertIsInstance(outcome_a.events, list)

    def test_pipeline_sink_requires_emit(self):
        with self.assertRaises(TypeError):
            DevModePipeline(sink=object()).run(
                make_context(
                    [{"path": "a.py", "language": "python",
                      "content": "def f():\n    pass\n"}]
                )
            )


def _plan():
    from core.actions import ActionPlan

    decision = _decision()
    action = _action()
    decision = decision.model_copy(
        update={"decision_id": "dec_plan", "proposed_actions": [action]}
    )
    return ActionPlan(
        user_id="usr_a",
        correlation_id="corr_plan",
        decision=decision,
        proposed_actions=[action],
        created_at=datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc),
    )


if __name__ == "__main__":
    unittest.main()