"""Deterministic bug detection (Phase 6).

Scans the supplied code files for *potential* bugs using honest, bounded,
language-aware pattern checks. Core Brain never claims certainty: every finding
carries a bounded confidence and "possible ..." language. An optional LLM
understanding can enrich the intent, NOT fabricate finding locations.
"""

from __future__ import annotations

from uuid import uuid4

from contracts.common.ids import UserId
from core.understanding.developer import DeveloperContext, language_of

from .checks import scan_file
from .exceptions import ReasoningValidationError
from .models import BugFinding, ReasoningLimits, ReviewCategory


def _new_finding_id() -> str:
    return f"bf_{uuid4().hex[:16]}"


class BugDetector:
    """Deterministic detection pass over changed / current files."""

    def __init__(self, limits: ReasoningLimits | None = None) -> None:
        self._limits = limits or ReasoningLimits()

    def detect(self, context: DeveloperContext) -> list[BugFinding]:
        if not isinstance(context, DeveloperContext):
            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        findings: list[BugFinding] = []
        for file in context.files:
            if len(findings) >= self._limits.max_findings:
                break
            language = file.language or language_of(file.path)
            for issue in scan_file(file.path, file.content, language=language):
                if issue.category != ReviewCategory.BUG:
                    continue
                findings.append(
                    BugFinding(
                        finding_id=_new_finding_id(),
                        user_id=context.user_id,
                        repository=context.repository,
                        file=file.path,
                        line=issue.line,
                        column=None,
                        title=issue.title,
                        message=issue.message,
                        severity=issue.severity,
                        confidence=issue.confidence,
                        check=issue.check,
                        suggested_fix=issue.suggestion,
                    )
                )
                if len(findings) >= self._limits.max_findings:
                    break
        return findings