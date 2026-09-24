"""Context Engine error hierarchy (Phase 4).

Mirrors the Phase 3 understanding module style: a single root tree with a
specific error per concern.
"""

from __future__ import annotations


class ContextError(Exception):
    """Base class for all Context Engine errors."""


class ContextEngineError(ContextError):
    """An error inside the Context Engine orchestration itself."""


class ContextValidationError(ContextError):
    """Invalid input to the Context Engine (bad model, bad limits, bad query)."""


class SearchError(ContextError):
    """The semantic-search layer failed and could not produce results."""