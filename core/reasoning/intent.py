"""Intent understanding (Phase 6).

Deterministic classification of what is requested / happening from the task
query and trusted DeveloperContext targets. Optional LLM understanding may only
enrich keywords — never the target file/line (anti-spoofing like other phases).
"""

from __future__ import annotations

import re

from core.understanding.developer import DeveloperContext

from .exceptions import ReasoningValidationError
from .models import IntentKind, IntentUnderstanding

_KEYWORD_GROUPS: list[tuple[IntentKind, tuple[str, ...]]] = [
    (IntentKind.BUG_DETECTION, (
        "bug", "issue", "crash", "error", "exception", "null", "segfault",
        "race", "wrong", "broken", "failing",
    )),
    (IntentKind.REVIEW, (
        "review", "pull request", "pr", "diff", "check my changes",
        "code review", "changes",
    )),
    (IntentKind.TEST, (
        "test", "tests", "pytest", "suite", "run tests", "coverage",
    )),
    (IntentKind.DEPLOY, (
        "deploy", "release", "ship", "production", "rollout", "staging",
    )),
    (IntentKind.FIX, (
        "fix", "repair", "resolve", "solve", "workaround",
    )),
    (IntentKind.EXPLAIN, (
        "explain", "what does", "how does", "why", "what is", "clarify",
    )),
]

_TASK_KEYS = ("task", "task_description", "request", "current_task")


class IntentAnalyzer:
    """Deterministic intent classification from query text."""

    def analyze(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
        extra_keywords: list[str] | None = None,
    ) -> IntentUnderstanding:
        if not isinstance(context, DeveloperContext):
            raise ReasoningValidationError(
                "context must be a DeveloperContext"
            )
        query = self._resolve_query(context, task)
        keywords: list[str] = []
        matched: list[str] = []
        lowered = query.lower()
        for kind, group in _KEYWORD_GROUPS:
            found = [
                word for word in group
                if re.search(rf"\b{re.escape(word)}\b", lowered)
            ]
            if found:
                keywords.extend(found)
                matched.append(kind)

        if len(matched) == 0:
            intent_kind = IntentKind.DEVELOPMENT
            confidence = 0.4 if query else 0.2
        else:
            intent_kind = matched[0]
            confidence = min(0.95, 0.5 + 0.1 * len(matched))

        for extra in extra_keywords or []:
            cleaned = str(extra).strip()
            if cleaned and cleaned not in keywords:
                keywords.append(cleaned)

        return IntentUnderstanding(
            user_id=context.user_id,
            query=query,
            intent_kind=intent_kind,
            confidence=round(confidence, 3),
            keywords=keywords[:20],
            repository=context.repository,
            target_file=context.current_file or self._first_changed(context),
            target_line=context.current_line,
            fallback_used=False,
        )

    @staticmethod
    def _resolve_query(context: DeveloperContext, task: str | None) -> str:
        if task and task.strip():
            return task.strip()
        for key in _TASK_KEYS:
            value = context.user_context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _first_changed(context: DeveloperContext) -> str | None:
        changed = [f for f in context.files if f.path in context.changed_files]
        if changed:
            return changed[0].path
        return context.files[0].path if context.files else None