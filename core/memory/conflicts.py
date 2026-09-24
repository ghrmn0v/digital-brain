"""Deterministic conflict detection and resolution (no LLM).

A "conflict" is scoped by a *conflict key*: a canonical identifier of the fact
two memories both claim. Memories sharing a key are mutually exclusive; the
newest (by creation, with ``valid_from`` tie-break) supersedes the earlier
ones. Everything else is left alone — there is NO generic
"everything conflicts with everything" behaviour.

Phase 1 conflict-key sources (first match wins):
    1. ``metadata["conflict_key"]``          -> explicit override, used verbatim
    2. domain table on (type, topic, person):
         FACT/EVENT metadata["topic"] in {employment, job, company, career, work}
             and related_people             -> "person:<pid>:employment"
         metadata["topic"] in {location, current_location, residence, city, address}
             and related_people             -> "person:<pid>:location"
         PREFERENCE metadata["preference"]  -> "user:<uid>:preference:<name>"
         RELATIONSHIP and related_people    -> "person:<pid>:relationship"
    3. otherwise                            -> no conflict domain (never conflicts)

What Phase 1 CANNOT detect (documented limitation): natural-language conflicts,
semantic similarity, or topics that arrive without the metadata hints above.
A future Understanding module will emit ``conflict_key`` explicitly.
"""

from __future__ import annotations

from typing import Any

from contracts.memory.memory import Memory, MemoryStatus, MemoryType

from .candidate import MemoryCandidate
from .temporal import end_for_successor, validate_memory_temporal

EXPLICIT_KEY = "conflict_key"

_EMPLOYMENT_TOPICS = {"employment", "job", "company", "career", "work"}
_LOCATION_TOPICS = {"location", "current_location", "residence", "city", "address"}


def conflict_key(memory: Memory | MemoryCandidate) -> str | None:
    """Return the canonical conflict key for a memory/candidate, or None."""
    metadata: dict[str, Any] = memory.metadata

    explicit = metadata.get(EXPLICIT_KEY)
    if explicit is not None:
        return str(explicit)

    memory_type = getattr(memory, "type", None)
    people = list(getattr(memory, "related_people", []))
    topic = metadata.get("topic")

    if (memory_type in (MemoryType.FACT, MemoryType.EVENT)) and topic in _EMPLOYMENT_TOPICS and people:
        return f"person:{people[0]}:employment"

    if topic in _LOCATION_TOPICS and people:
        return f"person:{people[0]}:location"

    if memory_type == MemoryType.PREFERENCE:
        preference = metadata.get("preference")
        if preference is not None:
            return f"user:{memory.user_id}:preference:{preference}"

    if memory_type == MemoryType.RELATIONSHIP and people:
        return f"person:{people[0]}:relationship"

    return None


def supersede_with(old: Memory, successor: Memory) -> Memory:
    """Return a copy of ``old`` marked as superseded by ``successor``.

    The old memory is NEVER erased: it keeps its id/content/history, gains
    status=SUPERSEDED, a bounded valid_until, and a pointer to its successor.
    """
    ended = end_for_successor(old, successor)
    updated = old.model_copy(
        update={
            "status": MemoryStatus.SUPERSEDED,
            "superseded_by": successor.memory_id,
            "valid_until": ended,
            "updated_at": successor.updated_at,
        }
    )
    validate_memory_temporal(updated)
    return updated