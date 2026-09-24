"""Deterministic importance baseline (Phase 1).

This is NOT machine learning. It is a transparent, documented rule table that
assigns importance in [0, 1]. Later learning phases may override importance,
but Phase 1 must remain deterministic and explainable.

Default baseline: 0.5.

Rules (additive, applied to a copy of the base):
    PREFERENCE                              +0.25   long-lived preferences matter
    RELATIONSHIP                            +0.20   people matter
    EVENT                                   +0.10
    INTERACTION                             -0.10   situational chatter
    has related_people                      +0.10
    metadata["explicit"] is True            +0.15   user explicitly stated it
    metadata["major_event"] is True         +0.20
    metadata["temporary"] is True           -0.30   contextual/throwaway
    confidence >= 0.9                       +0.05

Results are clamped to [0, 1].

An importance explicitly provided by the caller WINS (this is the seam where
future learning will inject its own scores).
"""

from __future__ import annotations

from contracts.memory.memory import MemoryType

from .candidate import MemoryCandidate
from .exceptions import MemoryValidationError

BASE_IMPORTANCE = 0.5


def baseline_importance(candidate: MemoryCandidate, confidence: float) -> float:
    """Compute the deterministic importance for a candidate."""
    if candidate.importance is not None:
        if not 0.0 <= candidate.importance <= 1.0:
            raise MemoryValidationError(
                f"importance must be within [0, 1], got {candidate.importance}"
            )
        return candidate.importance

    score = BASE_IMPORTANCE

    memory_type = candidate.type
    if memory_type == MemoryType.PREFERENCE:
        score += 0.25
    elif memory_type == MemoryType.RELATIONSHIP:
        score += 0.20
    elif memory_type == MemoryType.EVENT:
        score += 0.10
    elif memory_type == MemoryType.INTERACTION:
        score -= 0.10

    if candidate.related_people:
        score += 0.10

    metadata = candidate.metadata
    if metadata.get("explicit") is True:
        score += 0.15
    if metadata.get("major_event") is True:
        score += 0.20
    if metadata.get("temporary") is True:
        score -= 0.30
    if confidence >= 0.9:
        score += 0.05

    return min(1.0, max(0.0, score))