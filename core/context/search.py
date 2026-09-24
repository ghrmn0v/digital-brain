"""Semantic Search abstraction + deterministic lexical MVP (Phase 4).

``LexicalSemanticSearch`` is the initial provider-independent backer of the
:class:`SemanticSearch` port. A future ``EmbeddingSemanticSearch`` (behind a
vector store) can replace it without changing the Context Engine's public API.

The lexical implementation reuses ``MemoryService`` (port ``MemoryStore``); it
never writes memory and never bypasses user scoping.
"""

from __future__ import annotations

from typing import Callable
from datetime import datetime

from core.memory.filters import MemoryQuery

from .exceptions import ContextValidationError, SearchError
from .models import ScoredMemory, SearchQuery
from .ports import (  # re-exported for callers
    MemoryStore,
    SemanticSearch,
    UnderstandingPort,
)
from .ranking import Ranker

__all__ = [
    "LexicalSemanticSearch",
    "MemoryStore",
    "SemanticSearch",
    "UnderstandingPort",
]


class LexicalSemanticSearch:
    """Deterministic lexical semantic search over a ``MemoryStore``."""

    def __init__(
        self,
        memory_store: MemoryStore,
        *,
        ranker: Ranker | None = None,
        max_candidates: int = 500,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(memory_store, MemoryStore):
            raise TypeError("memory_store must implement MemoryStore (e.g. MemoryService)")
        if max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        self._store = memory_store
        self._ranker = ranker if ranker is not None else Ranker(now=now)
        self._max_candidates = max_candidates

    def search(self, query: SearchQuery) -> list[ScoredMemory]:
        """Rank the user's memories for a query (deterministic, bounded)."""
        if not isinstance(query, SearchQuery):
            raise ContextValidationError("query must be a SearchQuery")
        query.clean_keywords()

        filter_query = MemoryQuery(
            user_id=query.user_id,
            status=query.status,
            limit=self._max_candidates,
        )
        try:
            memories = self._store.list_memories(filter_query)
        except Exception as exc:  # port boundary: any store error degrades cleanly
            raise SearchError(f"memory store failure: {exc}") from exc

        results = self._ranker.rank(query, memories)
        if query.top_k is not None:
            results = results[: query.top_k]
        return results