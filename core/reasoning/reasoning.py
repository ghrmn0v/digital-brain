"""ReasoningEngine — the Phase 6 orchestration facade.

Composes intent understanding, bug detection, review and test interpretation
into one ``ReasoningResult`` for a DeveloperContext. Owns no memory and no
actions: it only *reasons*. An optional Understanding port may enrich intent
keywords; it NEVER fabricates finding locations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from core.understanding.developer import DeveloperContext

from .bug_detection import BugDetector
from .exceptions import ReasoningValidationError
from .intent import IntentAnalyzer
from .models import ReasoningLimits, ReasoningResult
from .review import CodeReviewer
from .test_interpretation import TestResultInterpreter


@runtime_checkable
class UnderstandingPort(Protocol):
    """Optional Phase 3 enrichment used to widen intent keywords."""

    def understand(
        self,
        corpus: str,
        *,
        user_id: str | None = None,
        corpus_id: str | None = None,
    ) -> "UnderstandingResult": ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReasoningEngine:
    """Facade over the deterministic reasoning passes."""

    def __init__(
        self,
        *,
        intent: IntentAnalyzer | None = None,
        bugs: BugDetector | None = None,
        review: CodeReviewer | None = None,
        tests: TestResultInterpreter | None = None,
        understanding: UnderstandingPort | None = None,
        limits: ReasoningLimits | None = None,
        now=None,
    ) -> None:
        self._limits = limits or ReasoningLimits()
        self._intent = intent or IntentAnalyzer()
        self._bugs = bugs or BugDetector(self._limits)
        self._review = review or CodeReviewer(self._limits)
        self._tests = tests or TestResultInterpreter(self._limits)
        self._understanding = understanding
        self._now = now or _utcnow

    def reason(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
    ) -> ReasoningResult:
        if not isinstance(context, DeveloperContext):
            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        keywords = self._enrich_keywords(context, task)

        intent = self._intent.analyze(
            context, task=task, extra_keywords=keywords
        )
        bugs = self._bugs.detect(context)
        review_findings = self._review.review(context)
        tests = self._tests.interpret(context)

        return ReasoningResult(
            user_id=context.user_id,
            repository=context.repository,
            created_at=self._now(),
            intent=intent,
            bugs=bugs,
            review_findings=review_findings,
            tests=tests,
            files_scanned=len(context.files),
            total_changed=len(set(context.changed_files or [])),
        )

    def _enrich_keywords(
        self, context: DeveloperContext, task: str | None
    ) -> list[str]:
        if self._understanding is None or not (task or "").strip():
            return []
        from core.understanding.exceptions import UnderstandingError

        try:
            result = self._understanding.understand(
                task.strip(),
                user_id=context.user_id,
                corpus_id=f"{context.repository}:{context.current_file or '<repo>'}",
            )
        except UnderstandingError:
            return []
        keywords: list[str] = []
        for value in (
            getattr(result, "entities", [])
            + getattr(result, "topics", [])
            + getattr(result, "relevant_code_concepts", [])
        ):
            cleaned = str(value).strip()
            if cleaned and cleaned not in keywords:
                keywords.append(cleaned)
        return keywords[:10]