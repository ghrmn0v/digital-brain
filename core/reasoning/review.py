"""Lightweight AI-assisted code review (Phase 6).

Deterministic findings over changed/current files (maintainability, security,
performance, test-coverage) plus the shared bug checks. Honest confidence —
no overclaiming. Specialised project-level checks (test coverage) live here.
"""

from __future__ import annotations

import re
from uuid import uuid4

from core.understanding.developer import DeveloperContext, language_of

from .checks import scan_file
from .exceptions import ReasoningValidationError
from .models import ReasoningLimits, ReviewCategory, ReviewFinding, Severity

_TEST_FILE = re.compile(
    r"(^|/)(test_|tests?/)|(_test\.|\.test\.|\.spec\.|_tests\.|_test\.)", re.IGNORECASE
)


def _new_finding_id() -> str:
    return f"rf_{uuid4().hex[:16]}"


class CodeReviewer:
    """Deterministic review pass, bounded and user-scoped."""

    def __init__(self, limits: ReasoningLimits | None = None) -> None:
        self._limits = limits or ReasoningLimits()

    def review(self, context: DeveloperContext) -> list[ReviewFinding]:
        if not isinstance(context, DeveloperContext):
            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        findings: list[ReviewFinding] = []

        def add(file_path: str, line: int, category: ReviewCategory,
                severity: Severity, explanation: str, confidence: float,
                suggestion: str | None) -> None:
            if len(findings) >= self._limits.max_review_findings:
                return
            findings.append(
                ReviewFinding(
                    finding_id=_new_finding_id(),
                    user_id=context.user_id,
                    repository=context.repository,
                    file=file_path,
                    line=line,
                    category=category,
                    severity=severity,
                    explanation=explanation,
                    confidence=confidence,
                    suggestion=suggestion,
                )
            )

        changed = set(context.changed_files or [])
        for file in context.files:
            if len(findings) >= self._limits.max_review_findings:
                break
            language = file.language or language_of(file.path)
            for issue in scan_file(file.path, file.content, language=language):
                if issue.category == ReviewCategory.BUG:
                    continue
                add(
                    file.path, issue.line, issue.category, issue.severity,
                    issue.message, issue.confidence, issue.suggestion,
                )
                if len(findings) >= self._limits.max_review_findings:
                    break

        self._coverage_check(context, changed, add)
        return findings

    def _coverage_check(
        self,
        context: DeveloperContext,
        changed: set[str],
        add,
    ) -> None:
        if not changed:
            return
        has_test_file = any(
            _TEST_FILE.search(file.path) for file in context.files
        )
        if has_test_file:
            return
        first_changed = next(
            (file for file in context.files if file.path in changed),
            None,
        )
        path = first_changed.path if first_changed else sorted(changed)[0]
        add(
            path,
            1,
            ReviewCategory.TEST_COVERAGE,
            Severity.WARNING,
            "Changed files ship without an accompanying test file in the "
            "supplied context.",
            0.5,
            "Add (or update) tests covering the changed behaviour.",
        )