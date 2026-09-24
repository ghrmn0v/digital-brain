"""Temporal validity rules for memories.

The Memory contract keeps history: ``valid_from`` / ``valid_until`` bound the
period a memory is true, and ``status`` records its lifecycle position. These
helpers enforce the rules and compute active/historical state WITHOUT an LLM.
"""

from __future__ import annotations

from datetime import datetime, timezone

from contracts.memory.memory import Memory, MemoryStatus

from .exceptions import TemporalValidityError


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def validate_memory_temporal(memory: Memory) -> None:
    """Raise TemporalValidityError if the memory's temporal fields are invalid."""
    if memory.valid_until is not None and memory.valid_until < memory.valid_from:
        raise TemporalValidityError(
            f"valid_until ({memory.valid_until}) is before valid_from "
            f"({memory.valid_from})"
        )


def is_active(memory: Memory, at: datetime | None = None) -> bool:
    """True when the memory is both marked ACTIVE and not expired at ``at``."""
    at = at or now_utc()
    if memory.status != MemoryStatus.ACTIVE:
        return False
    if memory.valid_until is not None and memory.valid_until <= at:
        return False
    return True


def end_for_successor(old: Memory, successor: Memory) -> datetime:
    """Valid period end for ``old`` once it is superseded by ``successor``.

    The old memory keeps validity until the successor's start (its own
    valid_until is never extended forward).
    """
    ended = successor.valid_from
    if ended < old.valid_from:
        ended = old.valid_from
    if old.valid_until is not None and old.valid_until < ended:
        ended = old.valid_until
    return ended