"""Learning errors (Phase 7)."""

from __future__ import annotations


class LearningError(Exception):
    """Base error for the learning/personalization layer."""


class LearningValidationError(LearningError):
    """Raised when feedback or learning input cannot be interpreted safely."""