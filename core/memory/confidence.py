"""Deterministic confidence handling.

Rule: a confidence explicitly provided by the caller is PRESERVED unchanged.
When absent, the engine assigns a documented baseline by provenance:

    user-provided (metadata["explicit"] or source.provider == "user")   0.95
    structured external source (linkedin/whatsapp/calendar/tasks/jobs)  0.70
    inferred (metadata["inferred"] is True)                             0.50
    conflicting evidence (metadata["conflicting_evidence"] is True)     0.40
    anything else / unknown provider                                    0.60

Confidence is NOT probabilistic inference — it is a stable baseline that the
producer's numeric value overrides whenever present.
"""

from __future__ import annotations

from contracts.memory.memory import Memory

from .candidate import MemoryCandidate
from .exceptions import MemoryValidationError

DEFAULT_CONFIDENCE = 0.60
EXPLICIT_CONFIDENCE = 0.95
EXTERNAL_CONFIDENCE = 0.70
INFERRED_CONFIDENCE = 0.50
CONFLICTING_CONFIDENCE = 0.40

_STRUCTURED_PROVIDERS = {
    "linkedin",
    "whatsapp",
    "calendar",
    "tasks",
    "jobs",
    "product",
}


def resolve_confidence(candidate: MemoryCandidate) -> float:
    """Return the confidence to store for a candidate."""
    if candidate.confidence is not None:
        if not 0.0 <= candidate.confidence <= 1.0:
            raise MemoryValidationError(
                f"confidence must be within [0, 1], got {candidate.confidence}"
            )
        return candidate.confidence

    metadata = candidate.metadata
    if metadata.get("conflicting_evidence") is True:
        return CONFLICTING_CONFIDENCE
    if metadata.get("inferred") is True:
        return INFERRED_CONFIDENCE
    if metadata.get("explicit") is True:
        return EXPLICIT_CONFIDENCE
    if candidate.source is not None:
        provider = candidate.source.provider
        if provider == "user":
            return EXPLICIT_CONFIDENCE
        if provider in _STRUCTURED_PROVIDERS:
            return EXTERNAL_CONFIDENCE
    return DEFAULT_CONFIDENCE