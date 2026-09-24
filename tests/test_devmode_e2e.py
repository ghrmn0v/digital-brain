"""End-to-end deterministic Developer Mode demo (Phase 6).

One integration test representing the hackathon demo:

1. Developer Mode context is supplied.
2. Repository contains a known potential bug.
3. Core Brain analyzes it.
4. Brain produces developer.bug_detected with repository/file/line/title/
   explanation/severity/confidence.
5. Brain creates a fix proposal (permission requested, nothing executed).
6. Test result can be supplied and interpreted.
7. Review finding can be generated.
8. Deployment can be proposed but never automatically executed.

No live LLM is used anywhere — all deterministic.
"""

from __future__ import annotations

import json
import unittest

from contracts.brain_events.events import BrainEvent, BrainEventType

from core import DevModePipeline
from core.understanding.developer import DeveloperContext

CODE = (
    "def get_user():\n"
    "    return None\n\n"
    "def render():\n"
    "    user = get_user()\n"
    "    print(user.email)\n"
    "    size = None\n"
    "    return 100 / size\n"
)


def demo_context() -> DeveloperContext:
    return DeveloperContext(
        user_id="usr_demo",
        repository="digital-brain",
        files=[{
            "path": "core/auth/login.py",
            "content": CODE,
            "language": "python",
        }],
        changed_files=["core/auth/login.py"],
        current_file="core/auth/login.py",
        current_line=7,
        git_context={"branch": "main"},
        user_context={
            "developer_mode": True,
            "task": "fix the null error in login render then review",
            "environment": "production",
        },
        test_results=[
            {"name": "test_login", "status": "failed",
             "file": "core/auth/login.py",
             "message": "Expected user object but received null"},
            {"name": "test_logout", "status": "passed"},
        ],
    )


class DevModeEndToEndDemoTests(unittest.TestCase):
    def test_hackathon_demo_flow(self):
        outcome = DevModePipeline().run(demo_context(), ask_deploy=False)

        self.assertEqual(outcome.user_id, "usr_demo")
        types = [e.type for e in outcome.events]

        # 1-4. bug detected with full location + explanation + confidence
        bugs = [
            e for e in outcome.events
            if e.type == BrainEventType.DEVELOPER_BUG_DETECTED
        ]
        self.assertGreaterEqual(len(bugs), 1)
        first = bugs[0]
        self.assertEqual(first.payload["repository"], "digital-brain")
        self.assertEqual(first.payload["file"], "core/auth/login.py")
        self.assertGreaterEqual(first.payload["line"], 1)
        self.assertTrue(first.payload["title"])
        self.assertTrue(first.payload["message"])
        self.assertIn(first.payload["severity"], ("info", "warning", "high", "critical"))
        self.assertGreater(first.payload["confidence"], 0.0)
        self.assertLess(first.payload["confidence"], 1.0)

        # 5. fix proposal requested, never executed
        fixes = [
            e for e in outcome.events
            if e.type == BrainEventType.DEVELOPER_FIX_PROPOSED
        ]
        self.assertGreaterEqual(len(fixes), 1)
        self.assertEqual(fixes[0].payload["affected_file"], "core/auth/login.py")
        self.assertIn("required_permission_level", fixes[0].payload)
        self.assertNotEqual(fixes[0].payload["required_permission_level"], "granted")
        for action in outcome.plan.proposed_actions:
            self.assertFalse(hasattr(action, "execute"))
            self.assertFalse(hasattr(action, "executed_at"))

        # 6. test result interpreted, never fabricated
        test_events = [
            e for e in outcome.events
            if e.type == BrainEventType.DEVELOPER_TEST_RESULT
        ]
        self.assertEqual(len(test_events), 1)
        self.assertEqual(test_events[0].payload["passed"], 1)
        self.assertEqual(test_events[0].payload["failed"], 1)
        self.assertIn("Expected user object", test_events[0].payload["reason"])

        # 7. review finding generated
        reviews = [
            e for e in outcome.events
            if e.type == BrainEventType.DEVELOPER_REVIEW_FINDING
        ]
        self.assertGreaterEqual(len(reviews), 1)
        self.assertIn(reviews[0].payload["category"],
                      ("bug", "maintainability", "test_coverage",
                       "security_concern", "performance_concern"))

        # correlation id shared across the whole pipeline
        self.assertTrue(
            all(e.payload.get("correlation_id") == outcome.correlation_id
                for e in outcome.events)
        )

    def test_demo_events_are_valid_contracts_and_serializable(self):
        outcome = DevModePipeline().run(demo_context(), ask_deploy=False)
        for event in outcome.events:
            model = BrainEvent.model_validate(event.model_dump())
            raw = json.loads(model.model_dump_json())
            self.assertEqual(raw["user_id"], "usr_demo")
            self.assertEqual(raw["type"], event.type.value)

    def test_strict_action_boundary_no_auto_effects(self):
        outcome = DevModePipeline().run(demo_context(), ask_deploy=True)
        deploy = [
            e for e in outcome.events
            if e.type == BrainEventType.DEVELOPER_DEPLOY_PROPOSED
        ]
        # deploy is PROPOSED only (permission requested), never executed
        if deploy:
            self.assertEqual(deploy[0].payload["environment"], "production")
            self.assertIn("required_permission_level", deploy[0].payload)
        self.assertNoExternalEffect(outcome)

    @staticmethod
    def assertNoExternalEffect(outcome) -> None:
        import types as _types
        for action in outcome.plan.proposed_actions:
            assert not hasattr(action, "execute"), "proposal must not execute"
            assert not callable(getattr(action, "execute", None))
        for event in outcome.events:
            payload = event.payload
            assert "executed" not in payload
            assert not payload.get("auto_ship")


if __name__ == "__main__":
    unittest.main()