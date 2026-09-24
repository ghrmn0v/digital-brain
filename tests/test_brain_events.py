"""Tests for Brain Events (Phase 6): event shapes, payloads, correlation and
pure-data behaviour for the Developer Mode pipeline."""

from __future__ import annotations

import unittest

from contracts.brain_events.events import BrainEventType

from core.brain_events import BrainEventEmitter, DevModePipeline
from core.reasoning import (
    BugFinding,
    ReviewCategory,
    ReviewFinding,
    Severity,
)
from core.reasoning.test_interpretation import TestResultInterpreter

from .test_actions import _fixable_context
from .test_reasoning import make_context


def _sample_finding(user_id="usr_a", line=3) -> BugFinding:
    return BugFinding(
        finding_id="bf_demo",
        user_id=user_id,
        repository="digital-brain",
        file="core/auth/login.py",
        line=line,
        title="Possible null reference",
        message="It may throw at runtime.",
        severity=Severity.HIGH,
        confidence=0.4,
        check="null_deref_check",
        suggested_fix="Add a guard.",
    )


class EmitterShapeTests(unittest.TestCase):
    def setUp(self):
        self.emitter = BrainEventEmitter()

    def test_bug_detected_payload_shape(self):
        event = self.emitter.bug_detected(
            _sample_finding(), correlation_id="corr_1"
        )
        self.assertEqual(event.type, BrainEventType.DEVELOPER_BUG_DETECTED)
        payload = event.payload
        for key in (
            "event_id", "repository", "file", "line", "column", "title",
            "message", "severity", "confidence", "correlation_id",
            "finding_id",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["line"], 3)
        self.assertEqual(payload["severity"], "high")
        self.assertEqual(payload["confidence"], 0.4)
        self.assertEqual(payload["correlation_id"], "corr_1")

    def test_test_result_payload_shape(self):
        interp = TestResultInterpreter().interpret(
            make_context(test_results=[
                {"name": "a", "status": "passed"},
                {"name": "b", "status": "failed", "message": "boom"},
            ])
        )
        event = self.emitter.test_result(interp, correlation_id="corr_1")
        self.assertEqual(event.type, BrainEventType.DEVELOPER_TEST_RESULT)
        for key in ("passed", "failed", "skipped", "errors", "summary",
                    "reason", "confidence", "correlation_id"):
            self.assertIn(key, event.payload)
        self.assertEqual(event.payload["passed"], 1)
        self.assertEqual(event.payload["failed"], 1)

    def test_review_finding_payload_shape(self):
        finding = ReviewFinding(
            finding_id="rf_1",
            user_id="usr_a",
            repository="digital-brain",
            file="login.py",
            line=4,
            category=ReviewCategory.TEST_COVERAGE,
            severity=Severity.WARNING,
            explanation="no tests",
            confidence=0.5,
            suggestion="add tests",
        )
        event = self.emitter.review_finding(finding, correlation_id="corr_1")
        self.assertEqual(event.type, BrainEventType.DEVELOPER_REVIEW_FINDING)
        self.assertEqual(event.payload["category"], "test_coverage")

    def test_events_have_unique_ids_and_source(self):
        e1 = self.emitter.bug_detected(_sample_finding(), correlation_id="c")
        e2 = self.emitter.bug_detected(_sample_finding(), correlation_id="c")
        self.assertNotEqual(e1.id, e2.id)
        self.assertEqual(e1.source.provider, "core")


class DevModePipelineTests(unittest.TestCase):
    def test_full_demo_event_pipeline(self):
        context = make_context(
            [
                {
                    "path": "core/auth/login.py",
                    "language": "python",
                    "content": (
                        "def get_user():\n"
                        "    return None\n\n"
                        "def render():\n"
                        "    user = get_user()\n"
                        "    return user.email\n"
                    ),
                }
            ],
            task="bug in login render",
            changed_files=["core/auth/login.py"],
            test_results=[
                {"name": "login", "status": "failed",
                 "message": "Expected user object but received null"},
            ],
        )
        outcome = DevModePipeline().run(context, task="bug in login render")
        types = [e.type for e in outcome.events]

        self.assertIn(BrainEventType.DEVELOPER_BUG_DETECTED, types)
        self.assertIn(BrainEventType.DEVELOPER_FIX_PROPOSED, types)
        self.assertIn(BrainEventType.DEVELOPER_TEST_RESULT, types)
        self.assertIn(BrainEventType.DEVELOPER_REVIEW_FINDING, types)

        bugged = [e for e in outcome.events if e.type == BrainEventType.DEVELOPER_BUG_DETECTED]
        self.assertTrue(bugged)
        for event in bugged:
            self.assertEqual(event.payload["repository"], "digital-brain")
            self.assertEqual(event.payload["file"], "core/auth/login.py")
            self.assertIn("title", event.payload)
            self.assertIn("message", event.payload)
            self.assertIn("severity", event.payload)

        self.assertTrue(
            all(
                e.payload.get("correlation_id") == outcome.correlation_id
                for e in outcome.events
            )
        )

    def test_pipeline_do_not_fabricate_test_results(self):
        context = make_context(
            [{"path": "a.py", "language": "python", "content": "def f():\n    pass\n"}]
        )
        outcome = DevModePipeline().run(context)
        for event in outcome.events:
            self.assertNotEqual(event.type, BrainEventType.DEVELOPER_TEST_RESULT)

    def test_deploy_proposed_only_when_asked_and_green(self):
        context = make_context(
            [
                {
                    "path": "ok.py",
                    "language": "python",
                    "content": "def f():\n    return 1 + 1\n",
                }
            ],
            changed_files=["ok.py"],
            test_results=[
                {"name": "t1", "status": "passed"},
                {"name": "t2", "status": "passed"},
            ],
        )
        plain = DevModePipeline().run(context)
        self.assertFalse(
            any(
                e.type == BrainEventType.DEVELOPER_DEPLOY_PROPOSED
                for e in plain.events
            )
        )
        ask = DevModePipeline().run(context, ask_deploy=True)
        deploy = [
            e for e in ask.events
            if e.type == BrainEventType.DEVELOPER_DEPLOY_PROPOSED
        ]
        self.assertEqual(len(deploy), 1)
        self.assertIn("environment", deploy[0].payload)
        self.assertIn("test_status", deploy[0].payload)

    def test_all_emitted_events_validate_as_contracts(self):
        context = _fixable_context()
        outcome = DevModePipeline().run(context, task="fix the bug")
        for event in outcome.events:
            self.assertIsNotNone(event.id)
            self.assertEqual(event.user_id, "usr_a")


if __name__ == "__main__":
    unittest.main()