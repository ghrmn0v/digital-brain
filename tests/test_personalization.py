"""Tests — Personalization profile (Phase 7)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)
from core.learning import (
    AssistanceProfile,
    LearningEngine,
    SqliteLearningStateRepository,
)
from core.people import PeopleIntelligence

from .memory_support import make_service


def ts() -> datetime:
    return datetime.now(timezone.utc)


def feedback(label, **meta):
    return Feedback(
        feedback_id=f"fb_{uuid4().hex[:12]}",
        user_id="usr_a",
        source=FeedbackSource.USER,
        kind=FeedbackKind.EXPLICIT,
        target=FeedbackTarget(action_id="act_1"),
        label=label,
        value=1.0 if label in ("accepted", "corrected") else -1.0,
        created_at=ts(),
        metadata=dict(meta),
    )


def make_profile():
    memory = make_service()
    people = PeopleIntelligence(memory, writer=memory)
    engine = LearningEngine(
        memory,
        writer=memory,
        state=SqliteLearningStateRepository(":memory:"),
        people=people,
    )
    return engine, people


class PersonalizationTests(unittest.TestCase):
    def test_empty_user_gets_blank_honest_profile(self):
        engine, _ = make_profile()
        profile = engine.personalization_profile("usr_a")
        self.assertIsInstance(profile, AssistanceProfile)
        self.assertEqual(profile.user_id, "usr_a")
        self.assertEqual(profile.feedback_count, 0)
        self.assertEqual(profile.top_affinities, [])
        self.assertEqual(profile.avoid_topics, [])
        self.assertEqual(profile.nudges, [])
        self.assertIsNone(profile.explanation_detail)

    def test_repeated_concise_acceptance_surfaces_nudge(self):
        engine, _ = make_profile()
        for _ in range(3):
            engine.record_feedback(
                feedback("accepted", topic="explanation:concise")
            )
        profile = engine.personalization_profile("usr_a")
        self.assertEqual(profile.feedback_count, 3)
        self.assertEqual(len(profile.nudges), 1)
        assert profile.nudges
        self.assertEqual(profile.nudges[0].direction, "positive")
        self.assertIn("concise", profile.nudges[0].suggestion)
        explanation = profile.explanation_detail
        self.assertIsNotNone(explanation)

    def test_rejected_topic_listed_as_avoid(self):
        engine, _ = make_profile()
        for _ in range(3):
            engine.record_feedback(
                feedback("rejected", topic="suggestion:code.review")
            )
        profile = engine.personalization_profile("usr_a")
        self.assertEqual(len(profile.avoid_topics), 1)
        self.assertEqual(profile.avoid_topics[0].topic, "suggestion:code.review")
        avoidance = [n for n in profile.nudges if n.direction == "negative"]
        self.assertEqual(len(avoidance), 1)
        self.assertIn("Avoid proposing", avoidance[0].suggestion)

    def test_mixed_evidence_keeps_rates_honest(self):
        engine, people = make_profile()
        for _ in range(2):
            engine.record_feedback(feedback("accepted", topic="tests"))
        for _ in range(1):
            engine.record_feedback(feedback("rejected", topic="tests"))
        profile = engine.personalization_profile("usr_a")
        self.assertEqual(len(profile.top_affinities), 1)
        top = profile.top_affinities[0]
        self.assertAlmostEqual(top.positive_rate, 2 / 3, places=3)

    def test_profile_is_deterministic(self):
        engine, _ = make_profile()
        for _ in range(3):
            engine.record_feedback(
                feedback("accepted", topic="explanation:concise")
            )
        first = engine.personalization_profile("usr_a")
        second = engine.personalization_profile("usr_a")
        self.assertEqual(
            first.model_dump(exclude={"generated_at"}),
            second.model_dump(exclude={"generated_at"}),
        )

    def test_isolation(self):
        engine, _ = make_profile()
        engine.record_feedback(
            feedback("accepted", topic="explanation:concise")
        )
        other = engine.personalization_profile("usr_b")
        self.assertEqual(other.feedback_count, 0)
        self.assertEqual(other.user_id, "usr_b")


if __name__ == "__main__":
    unittest.main()