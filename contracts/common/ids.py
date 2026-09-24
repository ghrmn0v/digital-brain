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

from pydantic import Field

EntityId = Annotated[str, Field(min_length=1, max_length=512)]
"""Minimal identifier for any entity exchanged between subsystems."""

UserId = Annotated[str, Field(min_length=1, max_length=512)]
"""The human user an event/memory/decision belongs to."""

PersonId = Annotated[str, Field(min_length=1, max_length=512)]
"""Identifies a person known to the Brain (see contract: people.Person)."""

EventId = Annotated[str, Field(min_length=1, max_length=512)]
"""Identifies a source or brain event."""

MemoryId = Annotated[str, Field(min_length=1, max_length=512)]
"""Identifies a Brain-owned memory record."""

DecisionId = Annotated[str, Field(min_length=1, max_length=512)]
"""Identifies a Brain decision."""

ActionId = Annotated[str, Field(min_length=1, max_length=512)]
"""Identifies a proposed action within a decision."""

FeedbackId = Annotated[str, Field(min_length=1, max_length=512)]
"""Identifies a feedback record."""