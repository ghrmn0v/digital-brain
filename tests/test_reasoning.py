"""Tests for Reasoning (Phase 6): intent, bug detection, review,
test interpretation and the ReasoningEngine facade."""

from __future__ import annotations

import unittest

from core.understanding.developer import DeveloperContext
from core.reasoning import (
    BugDetector,
    CodeReviewer,
    IntentKind,
    IntentAnalyzer,
    ReasoningEngine,
    ReasoningValidationError,
    Severity,
    TestResultInterpreter,
)


def make_context(
    files=None,
    *,
    user_id="usr_a",
    task=None,
    changed_files=None,
    test_results=None,
):
    return DeveloperContext(
        user_id=user_id,
        repository="digital-brain",
        files=files or [],
        changed_files=list(changed_files or []),
        current_file=(files[0]["path"] if files else None),
        git_context={"branch": "main"},
        user_context={"task": task} if task else {},
        test_results=list(test_results or []),
    )


class IntentTests(unittest.TestCase):
    def test_classifies_bug_detection(self):
        analyzer = IntentAnalyzer()
        files = [{"path": "core/auth/login.py", "language": "python",
                  "content": "def f():\n    pass\n"}]
        intent = analyzer.analyze(
            make_context(files, task="fix the null error in render")
        )
        self.assertEqual(intent.intent_kind, IntentKind.BUG_DETECTION)
        self.assertGreaterEqual(intent.confidence, 0.5)
        self.assertIn("null", intent.keywords)
        self.assertEqual(intent.target_file, "core/auth/login.py")

    def test_classifies_explain(self):
        intent = IntentAnalyzer().analyze(
            make_context(task="explain what this function does")
        )
        self.assertEqual(intent.intent_kind, IntentKind.EXPLAIN)

    def test_classifies_deploy(self):
        intent = IntentAnalyzer().analyze(
            make_context(task="deploy to production")
        )
        self.assertEqual(intent.intent_kind, IntentKind.DEPLOY)

    def test_defaults_to_development(self):
        intent = IntentAnalyzer().analyze(make_context(task="look around"))
        self.assertEqual(intent.intent_kind, IntentKind.DEVELOPMENT)

    def test_validates_context(self):
        with self.assertRaises(ReasoningValidationError):
            IntentAnalyzer().analyze(object())  # type: ignore[arg-type]


class BugDetectionTests(unittest.TestCase):
    def test_detects_possible_null_reference(self):
        files = [{
            "path": "core/auth/login.py",
            "language": "python",
            "content": (
                "def render():\n"
                "    user = get_user()\n"
                "    print(user.email)\n"
            ),
        }]
        findings = BugDetector().detect(make_context(files))
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.check, "null_deref_check")
        self.assertEqual(finding.line, 3)
        self.assertEqual(finding.file, "core/auth/login.py")
        self.assertEqual(finding.severity, Severity.HIGH)
        self.assertLess(finding.confidence, 0.5)
        self.assertIn("Possible null reference", finding.title)
        self.assertIsNotNone(finding.suggested_fix)

    def test_skips_null_reference_when_guarded(self):
        files = [{
            "path": "core/auth/login.py",
            "language": "python",
            "content": (
                "def render():\n"
                "    user = get_user()\n"
                "    if user is None:\n"
                "        return\n"
                "    print(user.email)\n"
            ),
        }]
        self.assertEqual(BugDetector().detect(make_context(files)), [])

    def test_detects_division_by_zero_unless_guarded(self):
        risky = [{
            "path": "x.py",
            "language": "python",
            "content": (
                "def f():\n"
                "    return total / count\n"
            ),
        }]
        self.assertEqual(len(BugDetector().detect(make_context(risky))), 1)

        safe = [{
            "path": "x.py",
            "language": "python",
            "content": (
                "def f():\n"
                "    if count == 0:\n"
                "        return 0\n"
                "    return total / count\n"
            ),
        }]
        self.assertEqual(BugDetector().detect(make_context(safe)), [])

    def test_findings_are_bounded(self):
        content = ""
        for i in range(30):
            content += (
                f"def f{i}():\n"
                f"    v{i} = get_user()\n"
                f"    return v{i}.email\n\n"
            )
        files = [{"path": "lots.py", "language": "python", "content": content}]
        findings = BugDetector().detect(make_context(files))
        self.assertLessEqual(len(findings), 40)


class ReviewTests(unittest.TestCase):
    def test_bare_except_and_coverage_reported(self):
        files = [
            {
                "path": "core/auth/login.py",
                "language": "python",
                "content": (
                    "def f(user):\n"
                    "    try:\n"
                    "        return user.email\n"
                    "    except:\n"
                    "        return ''\n"
                ),
            },
        ]
        findings = CodeReviewer().review(
            make_context(files, changed_files=["core/auth/login.py"])
        )
        categories = {f.category.value for f in findings}
        self.assertIn("maintainability", categories)
        self.assertIn("test_coverage", categories)

    def test_secret_literal_reported_as_security(self):
        files = [{
            "path": "config.py",
            "language": "python",
            "content": 'api_key = "sk-abcd1234secret"\n',
        }]
        findings = CodeReviewer().review(make_context(files, changed_files=["config.py"]))
        security = [
            f for f in findings if f.category.value == "security_concern"
        ]
        self.assertEqual(len(security), 1)
        self.assertEqual(security[0].line, 1)

    def test_coverage_skipped_when_test_file_present(self):
        files = [
            {"path": "login.py", "language": "python",
             "content": "def f():\n    return 1\n"},
            {"path": "tests/test_login.py", "language": "python",
             "content": "def test_f():\n    assert f()\n"},
        ]
        findings = CodeReviewer().review(
            make_context(files, changed_files=["login.py"])
        )
        self.assertFalse(
            any(f.category.value == "test_coverage" for f in findings)
        )


class TestInterpretationTests(unittest.TestCase):
    def test_summarizes_counts_and_failures(self):
        interp = TestResultInterpreter().interpret(
            make_context(
                test_results=[
                    {"name": "a", "status": "passed"},
                    {"name": "b", "status": "failed",
                     "message": "boom", "file": "t.py"},
                    {"name": "c", "status": "error", "message": "err"},
                    {"name": "d", "status": "skipped"},
                ]
            )
        )
        self.assertTrue(interp.provided)
        self.assertEqual(interp.passed, 1)
        self.assertEqual(interp.failed, 1)
        self.assertEqual(interp.skipped, 1)
        self.assertEqual(interp.errors, 1)
        self.assertIn("✓ 1 passed", interp.summary)
        self.assertIn("✗ 1 failed", interp.summary)
        self.assertEqual(interp.reason, "boom")
        self.assertEqual(len(interp.failures), 2)
        self.assertAlmostEqual(interp.confidence, 1 / 3, places=3)

    def test_empty_results_reported_as_not_provided(self):
        interp = TestResultInterpreter().interpret(make_context())
        self.assertFalse(interp.provided)
        self.assertEqual(interp.summary, "No test results supplied.")
        self.assertIsNone(interp.reason)
        self.assertEqual(interp.confidence, 0.0)


class ReasoningEngineTests(unittest.TestCase):
    def test_reason_aggregates_all_passes(self):
        files = [{
            "path": "core/auth/login.py",
            "language": "python",
            "content": (
                "def f():\n"
                "    user = get_user()\n"
                "    return user.email\n"
            ),
        }]
        result = ReasoningEngine().reason(
            make_context(
                files,
                task="bug in the login flow",
                changed_files=["core/auth/login.py"],
                test_results=[{"name": "t", "status": "failed"}],
            )
        )
        self.assertEqual(result.intent.intent_kind, IntentKind.BUG_DETECTION)
        self.assertEqual(len(result.bugs), 1)
        self.assertEqual(result.repository, "digital-brain")
        self.assertEqual(result.total_changed, 1)
        self.assertEqual(result.tests.failed, 1)

    def test_isolation_rejects_unrelated_context_type(self):
        with self.assertRaises(ReasoningValidationError):
            ReasoningEngine().reason("not a context")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()