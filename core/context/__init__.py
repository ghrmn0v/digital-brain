"""Core Brain Context Engine + Semantic Search (Phase 4).

The Context Engine is the layer between Memory/Understanding and future
Reasoning. It owns no memory storage; it consumes MemoryService through the
``SemanticSearch`` port so a future embedding/vector implementation can be
dropped in without changing the public API.
"""

from .engine import ContextEngine
from .exceptions import (
    ContextEngineError,
    ContextError,
    ContextValidationError,
    SearchError,
)
from .models import (
    Context,
    ContextLimits,
    ContextStatus,
    ScoredMemory,
    SearchMetadata,
    SearchQuery,
)
from .ports import MemoryStore, SemanticSearch, UnderstandingPort
from .ranking import RankConfig, Ranker
from .search import LexicalSemanticSearch

__all__ = [
    "Context",
    "ContextEngine",
    "ContextEngineError",
    "ContextError",
    "ContextLimits",
    "ContextStatus",
    "ContextValidationError",
    "LexicalSemanticSearch",
    "MemoryStore",
    "RankConfig",
    "Ranker",
    "ScoredMemory",
    "SearchError",
    "SearchMetadata",
    "SearchQuery",
    "SemanticSearch",
    "UnderstandingPort",
]