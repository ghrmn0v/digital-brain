"""Common identifiers shared by every Digital Brain contract.

All identifiers are non-empty strings, kept deliberately free-form so that
legacy/external systems are never rejected. Core Brain mints its own IDs with
a prefix so the owning subsystem is obvious at a glance:

    usr_  user            e.g. "usr_001"
    per_  person          e.g. "per_01H3AB.."
    evt_  source event    e.g. "evt_2026-01-01T00:00:00Z-ab12"
    mem_  memory          e.g. "mem_003"
    dec_  decision        e.g. "dec_017"
    fdb_  feedback        e.g. "fdb_009"

External systems NEVER mint these IDs. Their own identifiers live in
``ExternalIdentity.external_id`` instead.
"""

from typing import Annotated

from pydantic import AfterValidator, Field


def _not_blank(value: str) -> str:
    """Reject an identifier that carries no characters.

    ``min_length=1`` alone accepts ``" "``, which would silently create a
    phantom user namespace: a blank id is a *different* user from every real
    one, so it is a correctness and isolation problem, not a cosmetic one.
    Services already refused blank ids on the paths that went through People
    Intelligence; enforcing it here means every method inherits the rule and no
    new one can quietly forget it.

    The value is never rewritten — ``" a"`` stays distinct from ``"a"`` — only
    the blank case is refused.
    """
    if not value.strip():
        raise ValueError("identifier must not be blank")
    return value


_Identifier = Annotated[
    str,
    Field(min_length=1, max_length=512),
    AfterValidator(_not_blank),
]

EntityId = _Identifier
"""Minimal identifier for any entity exchanged between subsystems."""

UserId = _Identifier
"""The human user an event/memory/decision belongs to."""

PersonId = _Identifier
"""Identifies a person known to the Brain (see contract: people.Person)."""

EventId = _Identifier
"""Identifies a source or brain event."""

MemoryId = _Identifier
"""Identifies a Brain-owned memory record."""

DecisionId = _Identifier
"""Identifies a Brain decision."""

ActionId = _Identifier
"""Identifies a proposed action within a decision."""

FeedbackId = _Identifier
"""Identifies a feedback record."""