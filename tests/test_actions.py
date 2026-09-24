"""Tests for Action Planner (Phase 6): proposals are pure data, permission
levels are requested, nothing executes, user isolation holds."""

from __future__ import annotations

import unittest

from contracts.decisions.decisions import ActionType, PermissionLevel

from core.actions import ActionPlanner, ActionValidationError
from core.reasoning import ReasoningEngine

from .test_reasoning import make_context


def _reasoning_for(context, engine=None):
    return (engine or ReasoningEngine()).reason(context, task="fix the bug")


def _fixable_context():
    return make_context(
        [{
            "path": "core/auth/login.py",
            "language": "python",
            "content": (
                "def f():\n"
                "    user = get_user()\n"
                "    return user.email\n"
            ),
        }],
        changed_files=["core/auth/login.py"],
        test_results=[{"name": "t", "status": "failed"}],
    )


class ActionPlannerTests(unittest.TestCase):
    def test_proposals_are_pure_data_with_no_execution_surface(self):
        context = _fixable_context()
        reasoning = _reasoning_for(context)
        plan = ActionPlanner().plan(context, reasoning)
        self.assertTrue(plan.proposed_actions)
        for action in plan.proposed_actions:
            self.assertFalse(hasattr(action, "executed_at"))
            self.assertFalse(hasattr(action, "execute"))
        fix = [
            a for a in plan.proposed_actions
            if a.action_type == ActionType.CODE_FIX
        ]
        self.assertGreaterEqual(len(fix), 1)
        for action in fix:
            self.assertEqual(
                action.requested_permission_level, PermissionLevel.EXPLICIT
            )
            self.assertEqual(action.parameters["file"], "core/auth/login.py")
            self.assertIsNotNone(action.parameters["proposed_change"])

    def test_run_tests_proposed_on_failed_tests(self):
        context = _fixable_context()
        plan = ActionPlanner().plan(context, _reasoning_for(context))
        types = [p.action_type for p in plan.proposed_actions]
        self.assertIn(ActionType.RUN_TESTS, types)
        run_tests = next(p for p in plan.proposed_actions if p.action_type == ActionType.RUN_TESTS)
        self.assertEqual(run_tests.requested_permission_level, PermissionLevel.READ)

    def test_no_deploy_when_ask_deploy_false_or_red(self):
        context = _fixable_context()
        plan = ActionPlanner().plan(
            context, _reasoning_for(context), ask_deploy=True
        )
        types = [p.action_type for p in plan.proposed_actions]
        self.assertNotIn(ActionType.DEPLOY, types)

    def test_deploy_proposed_when_green_and_requested(self):
        context = make_context(
            [{"path": "ok.py", "language": "python",
              "content": "def f():\n    return 1 + 1\n"}],
            changed_files=["ok.py"],
            test_results=[
                {"name": "t1", "status": "passed"},
                {"name": "t2", "status": "passed"},
            ],
        )
        plan = ActionPlanner().plan(
            context,
            _reasoning_for(context),
            ask_deploy=True,
        )
        deploy = [p for p in plan.proposed_actions if p.action_type == ActionType.DEPLOY]
        self.assertEqual(len(deploy), 1)
        self.assertEqual(deploy[0].parameters["environment"], "staging")
        self.assertEqual(deploy[0].requested_permission_level, PermissionLevel.EXPLICIT)

    def test_empty_plan_when_no_signal(self):
        context = make_context(
            [{"path": "ok.py", "language": "python",
              "content": "def f():\n    return 1\n"}]
        )
        plan = ActionPlanner().plan(context, _reasoning_for(context))
        self.assertEqual(plan.proposed_actions, [])
        self.assertIn("No action warranted", plan.decision.reason)

    def test_decision_carries_context_summary(self):
        context = _fixable_context()
        plan = ActionPlanner().plan(context, _reasoning_for(context))
        self.assertTrue(plan.decision.decision_id.startswith("dec_"))
        self.assertEqual(plan.decision.context_summary["repository"], "digital-brain")
        self.assertGreater(plan.decision.confidence, 0.0)

    def test_correlation_id_shared_across_proposals(self):
        context = _fixable_context()
        plan = ActionPlanner().plan(context, _reasoning_for(context))
        ids = {p.correlation_id for p in plan.proposed_actions}
        self.assertEqual(ids, {plan.correlation_id})

    def test_proposals_bounded(self):
        context = make_context(
            [
                {
                    "path": f"f{i}.py",
                    "language": "python",
                    "content": (
                        f"def f{i}():\n"
                        f"    v = get_user()\n"
                        f"    return v.x\n"
                    ),
                }
                for i in range(10)
            ],
            changed_files=[f"f{i}.py" for i in range(10)],
            test_results=[{"name": "t", "status": "failed"}],
        )
        plan = ActionPlanner(max_proposals=3).plan(
            context, _reasoning_for(context)
        )
        self.assertLessEqual(len(plan.proposed_actions), 3)

    def test_isolation_rejects_mismatched_users(self):
        from core.actions import ActionPlanningError
        context = _fixable_context()
        other = context.model_copy(
            update={"user_id": "usr_other"}
        )
        reasoning = _reasoning_for(other)
        with self.assertRaises(ActionPlanningError):
            ActionPlanner().plan(context, reasoning)

    def test_construct_validation(self):
        with self.assertRaises(ActionValidationError):
            ActionPlanner(min_fix_confidence=2.0)
        with self.assertRaises(ActionValidationError):
            ActionPlanner(max_proposals=0)


if __name__ == "__main__":
    unittest.main()