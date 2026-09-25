"""End-to-end feedback loop (Phase 7) — Developer Mode + Learning.

Deterministic hackathon demo of the spec's final flow:

    developer.bug_detected → developer.fix_proposed → developer.test_result
    → developer.review_finding → feedback → learning

The pipeline proposes (never executes); the Product layer records feedback;
Core Brain turns it into a learned signal, preference + personalization the
next reasoning round can consume.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contracts.brain_events.events import BrainEventType
from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)

from core import DevModePipeline
from core.learning import LearningEngine, SqliteLearningStateRepository

from .memory_support import make_service
from .test_reasoning import make_context
from .test_devmode_e2e import CODE


def demo_pipeline_ctx():
    return make_context(
        [
            {
                "path": "core/auth/login.py",
                "language": "python",
                "content": CODE,
            }
        ],
        task="bug in login render",
        changed_files=["core/auth/login.py"],
        test_results=[
            {"name": "test_login", "status": "failed",
             "message": "Expected user object but received null"},
            {"name": "test_logout", "status": "passed"},
        ],
    )


class FeedbackLoopEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.memory = make_service()
        from core.people import PeopleIntelligence
        self.people = PeopleIntelligence(self.memory, writer=self.memory)
        self.engine = LearningEngine(
            self.memory,
            writer=self.memory,
            state=SqliteLearningStateRepository(":memory:"),
            people=self.people,
        )

    def _reject_fix(self, outcome, note="wrong target"):
        decision = outcome.plan.decision
        action = next(
            a for a in outcome.plan.proposed_actions
            if a.action_type.value == "code.fix"
        )
        return Feedback(
            feedback_id=f"fb_{datetime.now().timestamp()!r}",
            user_id=outcome.user_id,
            source=FeedbackSource.PRODUCT,
            kind=FeedbackKind.EXPLICIT,
            target=FeedbackTarget(
                decision_id=decision.decision_id,
                action_id=action.action_id,
            ),
            label="rejected",
            value=-1.0,
            note=note,
            created_at=datetime.now(timezone.utc),
            correlation_id=outcome.correlation_id,
            metadata={"action_type": "code.fix"},
        )

    def test_rejected_fix_learns_avoidance_for_code_fix(self):
        outcome = DevModePipeline().run(demo_pipeline_ctx(), task="bug in login render")
        types = [e.type for e in outcome.events]
        self.assertIn(BrainEventType.DEVELOPER_FIX_PROPOSED, types)

        for _ in range(3):
            stored = self.engine.record_feedback(self._reject_fix(outcome))
            self.assertIsNotNone(stored.memory_id)

        # learning aggregated + traced
        history = self.engine.feedback_history(outcome.user_id)
        self.assertEqual(len(history), 3)
        status = self.engine.learning_status(outcome.user_id)
        self.assertEqual(status.signal_counts["rejected"], 3)
        self.assertEqual(status.affinity("suggestion:code.fix").direction, "negative")

        # learned preference + personalization guidance exist, nothing executed
        prefs = self.people.preferences(outcome.user_id)
        self.assertTrue(any("avoid:suggestion:code.fix" == p.name for p in prefs))
        for action in outcome.plan.proposed_actions:
            self.assertFalse(hasattr(action, "execute"))
        profile = self.engine.personalization_profile(outcome.user_id)
        self.assertTrue(any(n.direction == "negative" for n in profile.nudges))

    def test_no_feedback_leaves_no_learning(self):
        outcome = DevModePipeline().run(demo_pipeline_ctx(), task="bug in login render")
        self.assertEqual(self.engine.learning_status(outcome.user_id).signal_counts, {})
        self.assertEqual(self.engine.feedback_history(outcome.user_id), [])

    def test_accepted_green_test_reinforces_testing_preference(self):
        outcome = DevModePipeline().run(demo_pipeline_ctx(), task="bug in login render")
        decision = outcome.plan.decision
        accepted = Feedback(
            feedback_id=f"fb_{datetime.now().timestamp()!r}",
            user_id=outcome.user_id,
            source=FeedbackSource.PRODUCT,
            kind=FeedbackKind.EXPLICIT,
            target=FeedbackTarget(decision_id=decision.decision_id),
            label="accepted",
            value=1.0,
            created_at=datetime.now(timezone.utc),
            correlation_id=outcome.correlation_id,
            metadata={"action_type": "code.fix", "tests_status": "green"},
        )
        self.engine.record_feedback(accepted)
        prefs = self.people.preferences(outcome.user_id)
        self.assertTrue(
            any(p.name == "fix-accepted-after-tests" for p in prefs)
        )

    def test_strict_action_boundary_never_broken(self):
        outcome = DevModePipeline().run(
            demo_pipeline_ctx(), task="bug in login render", ask_deploy=True
        )
        self.assertFalse(hasattr(outcome.plan.decision, "execute"))
        for action in outcome.plan.proposed_actions:
            self.assertFalse(hasattr(action, "executed_at"))
            self.assertFalse(hasattr(action, "execute"))


if __name__ == "__main__":
    unittest.main()