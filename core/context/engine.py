"""ContextEngine — assembles bounded, reasoning-ready Context (Phase 4).

Flow (matches the Developer Mode spec):

    DeveloperContext
        ↓
    Understanding (optional Phase 3 port)
        ↓
    ContextEngine.build_context(...)
        ↓
    Context        (→ Phase 6 Reasoning)

Design rules:

* The engine owns NO memory storage; it consumes ``SemanticSearch`` only.
* ``user_id`` always comes from the trusted ``DeveloperContext`` (never from
  nested/untrusted dicts or provider output) — same anti-spoofing as Phase 3.
* Queries, candidate counts, category lanes and totals are all bounded by
  ``ContextLimits``.
* Search failure produces a structured DEGRADED context (current context only,
  never fabricated memories); no relevant memories produce CURRENT_ONLY.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from contracts.common.ids import PersonId
from contracts.memory.memory import MemoryType
from core.memory.filters import MemoryStatusFilter
from core.understanding.developer import DeveloperContext
from core.understanding.exceptions import UnderstandingError

from .exceptions import ContextEngineError, ContextValidationError, SearchError
from .fields import is_bug_finding, is_decision
from .models import Context, ContextLimits, ContextStatus, SearchMetadata, SearchQuery, ScoredMemory
from .ports import SemanticSearch, UnderstandingPort

_TASK_KEYS = ("task", "task_description", "request", "current_task")


class ContextEngine:
    """Builds a bounded Context from a validated DeveloperContext."""

    def __init__(
        self,
        search: SemanticSearch,
        *,
        understanding: UnderstandingPort | None = None,
        limits: ContextLimits | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(search, SemanticSearch):
            raise TypeError("search must implement SemanticSearch")
        self._search = search
        self._understanding = understanding
        try:
            self._limits = (limits if limits is not None else ContextLimits()).validate()
        except ValueError as exc:
            raise ContextValidationError(str(exc)) from exc
        self._now = now or (lambda: datetime.now(timezone.utc))

    # -- public assembly ------------------------------------------------------
    def build_context(
        self,
        developer_context: DeveloperContext,
        *,
        task: str | None = None,
        status: MemoryStatusFilter = MemoryStatusFilter.ACTIVE,
        context_id: str | None = None,
    ) -> Context:
        if not isinstance(developer_context, DeveloperContext):
            raise ContextValidationError("developer_context must be a DeveloperContext")
        # Authoritative identity: never taken from nested dicts or provider output.
        user_id = developer_context.user_id

        current_task = self._resolve_task(developer_context, task)
        understanding = self._understand_if_possible(
            developer_context, current_task
        )
        keywords = self._keywords_of(understanding)

        query = SearchQuery(
            user_id=user_id,
            text=current_task or "",
            keywords=keywords,
            repository=developer_context.repository,
            current_file=developer_context.current_file,
            status=status,
            top_k=None,
        )
        try:
            results = self._search.search(query)
        except SearchError as exc:
            return self._degraded_context(
                developer_context, current_task, understanding, query, exc
            )

        final = self._assemble(results)
        people = self._gather_people(final)

        metadata = SearchMetadata(
            queries=[query.text],
            keywords=list(keywords),
            candidates_considered=getattr(
                self._search, "last_pool_size", len(results)
            ),
            repository_aware=bool(query.repository),
            file_aware=bool(query.current_file),
            status="ok",
            error=None,
        )
        return Context(
            context_id=context_id or f"ctx_{uuid4().hex[:16]}",
            user_id=user_id,
            repository=developer_context.repository,
            current_file=developer_context.current_file,
            current_line=developer_context.current_line,
            current_task=current_task,
            developer_context=developer_context,
            understanding=understanding,
            relevant_memories=[r for r in final if r is not None],
            previous_bug_findings=[
                r.memory.memory_id for r in final if is_bug_finding(r.memory)
            ],
            previous_decisions=[
                r.memory.memory_id for r in final if is_decision(r.memory)
            ],
            developer_preferences=[
                r.memory.memory_id
                for r in final
                if r.memory.type == MemoryType.PREFERENCE
            ],
            relevant_people=people,
            search_metadata=metadata,
            status=ContextStatus.FULL if final else ContextStatus.CURRENT_ONLY,
            fallback_used=bool(understanding and understanding.fallback_used),
            created_at=self._now(),
        )

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _resolve_task(
        developer_context: DeveloperContext, task: str | None
    ) -> str | None:
        if task and task.strip():
            return task.strip()
        for key in _TASK_KEYS:
            value = developer_context.user_context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _understand_if_possible(
        self,
        developer_context: DeveloperContext,
        current_task: str | None,
    ):
        if self._understanding is None or not current_task:
            return None
        try:
            return self._understanding.understand(
                current_task,
                user_id=developer_context.user_id,
                corpus_id=(
                    f"{developer_context.repository}:"
                    f"{developer_context.current_file or '<repo>'}"
                ),
            )
        except UnderstandingError:
            return None

    @staticmethod
    def _keywords_of(understanding) -> list[str]:
        if understanding is None:
            return []
        keywords: list[str] = []
        for value in (
            getattr(understanding, "entities", [])
            + getattr(understanding, "topics", [])
            + getattr(understanding, "relevant_code_concepts", [])
        ):
            cleaned = str(value).strip()
            if cleaned and cleaned not in keywords:
                keywords.append(cleaned)
        return keywords

    def _assemble(
        self, results: list[ScoredMemory]
    ) -> list[ScoredMemory]:
        final: list[ScoredMemory] = []
        added: set[str] = set()
        limits = self._limits

        def add(result: ScoredMemory) -> None:
            if result.memory.memory_id in added:
                return
            if len(final) >= limits.max_total_memories:
                return
            final.append(result)
            added.add(result.memory.memory_id)

        bug_seen = decision_seen = preference_seen = 0
        for result in results:
            if (
                is_bug_finding(result.memory)
                and result.score >= limits.category_min_score
                and bug_seen < limits.top_bug_findings
            ):
                add(result)
                bug_seen += 1
            if (
                is_decision(result.memory)
                and result.score >= limits.category_min_score
                and decision_seen < limits.top_decisions
            ):
                add(result)
                decision_seen += 1
            if (
                result.memory.type == MemoryType.PREFERENCE
                and result.score >= limits.category_min_score
                and preference_seen < limits.top_preferences
            ):
                add(result)
                preference_seen += 1

        for result in results:
            add(result)

        return final

    def _gather_people(self, final: list[ScoredMemory]) -> list[PersonId]:
        people: list[PersonId] = []
        for result in final:
            for person_id in result.memory.related_people:
                if person_id not in people:
                    people.append(person_id)
                if len(people) >= self._limits.max_people:
                    break
            if len(people) >= self._limits.max_people:
                break
        return people

    def _degraded_context(
        self,
        developer_context: DeveloperContext,
        current_task: str | None,
        understanding,
        query: SearchQuery,
        error: SearchError,
    ) -> Context:
        metadata = SearchMetadata(
            queries=[query.text],
            keywords=list(query.keywords),
            candidates_considered=0,
            repository_aware=bool(query.repository),
            file_aware=bool(query.current_file),
            status="degraded",
            error=str(error),
        )
        return Context(
            context_id=f"ctx_{uuid4().hex[:16]}",
            user_id=developer_context.user_id,
            repository=developer_context.repository,
            current_file=developer_context.current_file,
            current_line=developer_context.current_line,
            current_task=current_task,
            developer_context=developer_context,
            understanding=understanding,
            relevant_memories=[],
            search_metadata=metadata,
            status=ContextStatus.DEGRADED,
            fallback_used=bool(understanding and understanding.fallback_used),
            created_at=self._now(),
        )