"""Deterministic memory classification.

Phase 1 is rule-based and has NO LLM dependency. The classifier stays a small
object so a later LLM-assisted classifier can replace it behind the same
:meth:`MemoryClassifier.classify` interface.

The produced ``MemoryType`` is always a value of the Phase 0 Memory contract
enum. The spec's "PERSON / TASK_CONTEXT / OTHER" names are mapped onto the
contract types that exist today:

    PERSON       -> FACT        (a person fact, optionally with related_people)
    TASK_CONTEXT -> EPISODE     (a bounded, situational segment)
    OTHER        -> OBSERVATION (recorded but unclassified)

Rules (first match wins):
    1. ``candidate.type`` provided and valid                       -> use as-is
    2. ``metadata["kind"]`` of:
           preference   -> PREFERENCE
           relationship -> RELATIONSHIP
           interaction|conversation -> INTERACTION
           episode|task|task_context -> EPISODE
           event        -> EVENT
           fact         -> FACT
           anything else -> OBSERVATION  (unknown, keep open)
    3. ``metadata["temporary"] is True` -> EPISODE
    4. otherwise                        -> FACT (default: stable statement)
"""

from __future__ import annotations

from contracts.memory.memory import MemoryType

from .candidate import MemoryCandidate

_KIND_RULES: dict[str, MemoryType] = {
    "preference": MemoryType.PREFERENCE,
    "relationship": MemoryType.RELATIONSHIP,
    "interaction": MemoryType.INTERACTION,
    "conversation": MemoryType.INTERACTION,
    "episode": MemoryType.EPISODE,
    "task": MemoryType.EPISODE,
    "task_context": MemoryType.EPISODE,
    "event": MemoryType.EVENT,
    "fact": MemoryType.FACT,
}


class MemoryClassifier:
    """Deterministic classifier (replaceable by an LLM-assisted one later)."""

    def classify(self, candidate: MemoryCandidate) -> MemoryType:
        if candidate.type is not None:
            return candidate.type

        kind = candidate.metadata.get("kind")
        if kind is not None:
            return _KIND_RULES.get(str(kind), MemoryType.OBSERVATION)

        if candidate.metadata.get("temporary") is True:
            return MemoryType.EPISODE

        return MemoryType.FACT