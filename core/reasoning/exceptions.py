"""Reasoning errors (Phase 6)."""

from __future__ import annotations


class ReasoningError(Exception):
    """Base class for all Reasoning errors."""


class ReasoningValidationError(ReasoningError):
    """Invalid input to Reasoning (bad context, bad limits)."""


class IntentAnalysisError(ReasoningError):
    """Intent understanding failed."""