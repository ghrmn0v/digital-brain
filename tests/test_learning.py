"""Tests — Feedback→Signal interpretation + Learning Engine (Phase 7)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contracts.common.types import Source
from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)
from core.learning import (
    FeedbackInterpreter,
    LearningEngine,
    LearningStatus,
    LearningValidationError,
    SignalKind,
    SqliteLearningStateRepository,
)
from core.people import PeopleIntelligence
from core.people.models import PreferenceDomain

from .memory_support import make_service


def ts() -> datetime:
    return datetime.now(timezone.utc)


def make_feedback(
    *,
    user_id="usr_a",
    label=None,
    value=None,
    kind=FeedbackKind.EXPLICIT,
    source=FeedbackSource.USER,
    target=None,
    metadata=None,
    note=None,
):
    return Feedback(
        feedback_id=f"fb_{uuid4().hex[:12]}",
        user_id=user_id,
        source=source,
        kind=kind,
        target=target or FeedbackTarget(action_id="act_1"),
        value=value,
        label=label,
        note=note,
        created_at=ts(),
        correlation_id="corr_1",
        metadata=dict(metadata or {}),
    )


def make_engine(user_id="usr_a"):
    memory = make_service()
    people = PeopleIntelligence(memory, writer=memory)
    engine = LearningEngine(
        memory,
        writer=memory,
        state=SqliteLearningStateRepository(":memory:"),
        people=people,
        updater=memory,
    )
    return engine, memory, people


class InterpreterTests(unittest.TestCase):
    def setUp(self):
        self.interpreter = FeedbackInterpreter()

    def test_label_maps_to_kind(self):
        accepted = self.interpreter.interpret(
            make_feedback(label="accepted")
        )
        self.assertEqual(accepted.kind, SignalKind.ACCEPTED)
        self.assertGreater(accepted.strength, 0)
        self.assertGreater(accepted.delta_importance, 0)

        rejected = self.interpreter.interpret(
            make_feedback(label="rejected", value=-1.0)
        )
        self.assertEqual(rejected.kind, SignalKind.REJECTED)
        self.assertLess(rejected.delta_importance, 0)

    def test_outcome_and_reward(self):
        outcome = self.interpreter.interpret(
            make_feedback(
                kind=FeedbackKind.OUTCOME, label="unsuccessful"  # noqa: E501
            )
        )
        self.assertEqual(outcome.kind, SignalKind.UNSUCCESSFUL)

        reward = self.interpreter.interpret(
            make_feedback(
                kind=FeedbackKind.REWARD, value=0.6, label=None
            )
        )
        self.assertEqual(reward.kind, SignalKind.SUCCESSFUL)

    def test_signal_override_wins(self):
        signal = self.interpreter.interpret(
            make_feedback(label="accepted", metadata={"signal": "ignored"})
        )
        self.assertEqual(signal.kind, SignalKind.IGNORED)
        self.assertEqual(signal.delta_importance, 0.0)

    def test_unreadable_raises(self):
        with self.assertRaises(LearningValidationError):
            self.interpreter.interpret(
                make_feedback(kind=FeedbackKind.EXPLICIT, label=None, value=None)
            )

    def test_topic_and_preference_hint(self):
        signal = self.interpreter.interpret(
            make_feedback(
                label="accepted",
                metadata={"topic": "explanation:concise"},
            )
        )
        self.assertEqual(signal.topic, "explanation:concise")
        self.assertEqual(
            signal.preference_domain, PreferenceDomain.EXPLANATION_DETAIL
        )

        fallback = self.interpreter.interpret(
            make_feedback(label="accepted", metadata={"action_type": "code.fix"})
        )
        self.assertEqual(fallback.topic, "suggestion:code.fix")

    def test_tests_status_parsed(self):
        green = self.interpreter.interpret(
            make_feedback(label="accepted", metadata={"tests_status": "green"})
        )
        self.assertTrue(green.tests_were_green)


class LearningEngineTests(unittest.TestCase):
    def test_records_trace_and_history_roundtrip(self):
        engine, memory, people = make_engine()
        feedback = make_feedback(
            label="corrected", metadata={"topic": "explanation:concise"}
        )
        engine.record_feedback(feedback)

        history = engine.feedback_history("usr_a")
        self.assertEqual(len(history), 1)
        stored = history[0]
        self.assertEqual(stored.feedback.feedback_id, feedback.feedback_id)
        self.assertEqual(stored.signal.kind, SignalKind.CORRECTED)
        self.assertTrue(stored.memory_id)
        self.assertEqual(stored.signal.topic, "explanation:concise")

    def test_state_counts_and_affinity(self):
        engine, _, _ = make_engine()
        for _ in range(2):
            engine.record_feedback(
                make_feedback(label="accepted", metadata={"topic": "run-tests"})
            )
        for _ in range(3):
            engine.record_feedback(
                make_feedback(label="rejected", metadata={"topic": "deploy"})
            )
        status = engine.learning_status("usr_a")
        self.assertEqual(status.signal_counts["accepted"], 2)
        self.assertEqual(status.signal_counts["rejected"], 3)
        run_tests = status.affinity("run-tests")
        deploy = status.affinity("deploy")
        self.assertEqual(run_tests.direction, "positive")
        self.assertEqual(run_tests.positive_rate, 1.0)
        self.assertEqual(deploy.direction, "negative")
        self.assertEqual(deploy.positive_rate, 0.0)

    def test_repeated_rejection_learns_avoid_preference(self):
        engine, _, people = make_engine()
        for _ in range(3):
            engine.record_feedback(
                make_feedback(label="rejected", metadata={"topic": "suggestion:code.fix"})
            )
        prefs = people.preferences("usr_a")
        avoid = [p for p in prefs if p.name == "avoid:suggestion:code.fix"]
        self.assertEqual(len(avoid), 1)
        self.assertIn("avoided after 3 rejection(s)", avoid[0].value)

    def test_repeated_acceptance_learns_preference(self):
        engine, _, people = make_engine()
        for _ in range(3):
            engine.record_feedback(
                make_feedback(
                    label="accepted",
                    metadata={"topic": "explanation:concise"},
                )
            )
        prefs = people.preferences("usr_a")
        explanation = [
            p for p in prefs
            if p.domain == PreferenceDomain.EXPLANATION_DETAIL
            and p.name == "explanation"
        ]
        self.assertEqual(len(explanation), 1)
        self.assertGreaterEqual(explanation[0].importance, 0.3)

    def test_green_tests_acceptance_recorded(self):
        engine, _, people = make_engine()
        engine.record_feedback(
            make_feedback(
                label="accepted",
                metadata={"tests_status": "green", "topic": "suggestion:code.fix"},
            )
        )
        prefs = people.preferences("usr_a")
        self.assertTrue(
            any(p.name == "fix-accepted-after-tests" for p in prefs)
        )

    def test_importance_learned_with_updater(self):
        engine, memory, _ = make_engine()
        from core.memory.candidate import MemoryCandidate
        created = memory.create_memory(
            MemoryCandidate(
                content="the old code fix",
                user_id="usr_a",
                source=Source(provider="test"),
                importance=0.4,
            )
        )
        engine.record_feedback(
            make_feedback(
                label="accepted",
                target=FeedbackTarget(memory_id=created.memory_id),
            )
        )
        updated = memory.get_memory("usr_a", created.memory_id)
        self.assertGreater(updated.importance, created.importance)

        engine.record_feedback(
            make_feedback(
                label="rejected",
                target=FeedbackTarget(memory_id=created.memory_id),
            )
        )
        updated = memory.get_memory("usr_a", created.memory_id)
        self.assertLess(updated.importance, created.importance)

    def test_isolation_between_users(self):
        engine, _, _ = make_engine()
        engine.record_feedback(make_feedback(user_id="usr_a", label="accepted"))
        self.assertEqual(engine.learning_status("usr_b").signal_counts, {})
        self.assertEqual(engine.feedback_history("usr_b"), [])
        history = engine.feedback_history("usr_a")
        self.assertEqual(len(history), 1)

    def test_feedback_history_limit(self):
        engine, _, _ = make_engine()
        for _ in range(3):
            engine.record_feedback(make_feedback(label="accepted"))
        self.assertEqual(len(engine.feedback_history("usr_a", limit=2)), 2)

    def test_validation_of_ports(self):
        with self.assertRaises(LearningValidationError):
            LearningEngine(
                memory=object(),  # type: ignore[arg-type]
                writer=object(),  # type: ignore[arg-type]
                state=object(),  # type: ignore[arg-type]
            )

    def test_record_requires_real_feedback(self):
        engine, _, _ = make_engine()
        with self.assertRaises(LearningValidationError):
            engine.record_feedback("accepted")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()