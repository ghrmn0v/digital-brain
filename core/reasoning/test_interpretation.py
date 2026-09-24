"""Test-result interpretation (Phase 6).

Core Brain summarizes test results EXACTLY as reported — the interpreter never
fabricates a pass/fail. Input is the structured ``DeveloperContext.test_results``
snapshot supplied by the Product layer.
"""

from __future__ import annotations

from core.understanding.developer import DeveloperContext

from .exceptions import ReasoningValidationError
from .models import ReasoningLimits, TestFailure, TestResultInterpretation


class TestResultInterpreter:
    """Deterministic summarization of structured test results."""

    def __init__(self, limits: ReasoningLimits | None = None) -> None:
        self._limits = limits or ReasoningLimits()

    def interpret(
        self, context: DeveloperContext
    ) -> TestResultInterpretation:
        if not isinstance(context, DeveloperContext):
            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        provided = bool(context.test_results)
        passed = failed = skipped = errors = 0
        failures: list[TestFailure] = []
        for result in context.test_results:
            if result.status == "passed":
                passed += 1
            elif result.status == "failed":
                failed += 1
                if len(failures) < self._limits.max_failed_detail:
                    failures.append(
                        TestFailure(
                            name=result.name,
                            file=result.file,
                            message=result.message,
                        )
                    )
            elif result.status == "skipped":
                skipped += 1
            else:  # "error"
                errors += 1
                if len(failures) < self._limits.max_failed_detail:
                    failures.append(
                        TestFailure(
                            name=result.name,
                            file=result.file,
                            message=result.message,
                        )
                    )

        if not provided:
            summary = "No test results supplied."
            reason = None
            confidence = 0.0
        else:
            summary = (
                f"Tests: ✓ {passed} passed, ✗ {failed} failed, "
                f"{skipped} skipped, {errors} errors"
            )
            reason = (
                failures[0].message if failures and failures[0].message else None
            )
            total = passed + failed + errors
            confidence = round(passed / total, 3) if total else 0.0

        return TestResultInterpretation(
            user_id=context.user_id,
            repository=context.repository,
            provided=provided,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            summary=summary,
            reason=reason,
            failures=failures,
            confidence=confidence,
        )