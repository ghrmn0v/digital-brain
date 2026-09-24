"""Context Engine ports (abstractions the engine depends on).

The Context Engine owns NO memory storage. It consumes memories through a
Memory-backed search port; a future embedding/vector implementation can replace
the lexical searcher behind the same :class:`SemanticSearch` port without
touching the engine or its public API.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.memory.memory import Memory
from core.memory.filters import MemoryQuery
from core.understanding.models import UnderstandingResult

from .models import ScoredMemory, SearchQuery


@runtime_checkable
class MemoryStore(Protocol):
    """A memory source the search layer reads through (never writes).

    ``MemoryService`` satisfies this port unchanged — the Context Engine never
    bypasses it.
    """

    def list_memories(self, query: MemoryQuery) -> list[Memory]: ...


@runtime_checkable
class SemanticSearch(Protocol):
    """Deterministic relevance search over a user's memories."""

    def search(self, query: SearchQuery) -> list[ScoredMemory]: ...


@runtime_checkable
class UnderstandingPort(Protocol):
    """Optional Phase 3 enrichment used to expand search queries.

    ``core.understanding.LLMGateway`` satisfies this port.
    """

    def understand(
        self,
        corpus: str,
        *,
        user_id: str | None = None,
        corpus_id: str | None = None,
    ) -> "UnderstandingResult": ...