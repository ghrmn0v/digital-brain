"""ReasoningEngine — the Phase 6 orchestration facade.

Composes intent understanding, bug detection, review and test interpretation
into one ``ReasoningResult`` for a DeveloperContext. Owns no memory and no
actions: it only *reasons*. An optional Understanding port may enrich intent
keywords; it NEVER fabricates finding locations.

Phase 8 Slice 2: an optional distilled :class:`ReasoningContext` (from the
Context Engine) and an optional read-only :class:`LearningProfilePort` (learned
personalization) may enter a reasoning round. Without either, behavior is
byte-for-byte unchanged. Nothing here infers learning; the profile is only
copied, and avoided topics only suppress exact keyword suggestions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from core.understanding.developer import DeveloperContext

from .bug_detection import BugDetector
from .context import context_keywords
from .exceptions import ReasoningValidationError
from .intent import IntentAnalyzer
from .models import (
    LearningInfluence,
    ReasoningContext,
    ReasoningLimits,
    ReasoningResult,
)
from .ports import LearningProfilePort
from .profiles import build_learning_influence
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


def _avoided_words(influence: LearningInfluence) -> frozenset[str]:
    """Deterministic base words extracted from learned avoid-topics.

    Splits ``topic`` on ``:``/``_``/whitespace and keeps words of length 3..40.
    Only exact matches against these explicit words are suppressed.
    """
    words: set[str] = set()
    for topic in influence.avoid_topics:
        for part in re.split(r"[:_\s]+", topic):
            part = part.strip().lower()
            if 3 <= len(part) <= 40:
                words.add(part)
    return frozenset(words)


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
        learning: LearningProfilePort | None = None,
        limits: ReasoningLimits | None = None,
        now=None,
    ) -> None:
        self._limits = limits or ReasoningLimits()
        self._intent = intent or IntentAnalyzer()
        self._bugs = bugs or BugDetector(self._limits)
        self._review = review or CodeReviewer(self._limits)
        self._tests = tests or TestResultInterpreter(self._limits)
        self._understanding = understanding
        self.learning = learning
        self._now = now or _utcnow

    def reason(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
        reasoning_context: ReasoningContext | None = None,
    ) -> ReasoningResult:
        if not isinstance(context, DeveloperContext):
            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        if reasoning_context is not None:
            if not isinstance(reasoning_context, ReasoningContext):
                raise ReasoningValidationError(
                    "reasoning_context must be a ReasoningContext"
                )
            if reasoning_context.user_id != context.user_id:
                raise ReasoningValidationError(
                    "reasoning_context.user_id must match the "
                    "DeveloperContext user_id"
                )

        keywords = self._enrich_keywords(context, task, reasoning_context)
        learning = self._apply_learning(context.user_id, keywords)

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
            context=reasoning_context,
            learning=learning,
        )

    def _enrich_keywords(
        self,
        context: DeveloperContext,
        task: str | None,
        reasoning_context: ReasoningContext | None,
    ) -> list[str]:
        keywords: list[str] = []
        if self._understanding is not None and (task or "").strip():
            from core.understanding.exceptions import UnderstandingError

            try:
                result = self._understanding.understand(
                    task.strip(),
                    user_id=context.user_id,
                    corpus_id=f"{context.repository}:{context.current_file or '<repo>'}",
                )
            except UnderstandingError:
                result = None
            for value in (
                getattr(result, "entities", [])
                + getattr(result, "topics", [])
                + getattr(result, "relevant_code_concepts", [])
            ):
                cleaned = str(value).strip()
                if cleaned and cleaned not in keywords:
                    keywords.append(cleaned)

        for token in context_keywords(reasoning_context):
            if token not in keywords:
                keywords.append(token)
        return keywords[:20]

    def _apply_learning(
        self,
        user_id: str,
        keywords: list[str],
    ) -> LearningInfluence | None:
        """Consult the read-only learning port and apply explicit rules only.

        Returns ``None`` when no port is configured (or it cannot produce a
        profile) so absent learning never breaks reasoning. When a profile
        exists, keyword suggestions that match a learned avoided topic are
        dropped one-for-one — never invented, always bounded.
        """
        if self.learning is None:
            return None
        try:
            profile = self.learning.personalization_profile(user_id)
        except Exception:
            return None
        if profile is None:
            return None
        influence = build_learning_influence(profile)
        avoided = _avoided_words(influence)
        if avoided:
            keywords[:] = [
                keyword
                for keyword in keywords
                if keyword not in avoided
            ]
        return influence