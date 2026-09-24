"""Public value types produced by the ingestion pipeline.

The pipeline never raises for ordinary outcomes: every event maps to exactly
one :class:`IngestionResult`. ``PROCESSING_FAILED`` is part of the outcome
enum so failures are explicit rather than silently swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from contracts.common.ids import EventId, MemoryId, UserId


class IngestionOutcome(str, Enum):
    """Lifecycle outcome of a single ingested event."""

    ACCEPTED = "accepted"
    """Event was valid, processed (possibly into memories) and receipted."""

    DUPLICATE = "duplicate"
    """An identical logical event was already accepted for this user."""

    REJECTED = "rejected"
    """Event failed schema or business validation; nothing was stored."""

    PROCESSING_FAILED = "processing_failed"
    """The event was valid but could not be processed/persisted."""


@dataclass(frozen=True)
class IngestionResult:
    """Structured outcome of :meth:`IngestionService.ingest`."""

    outcome: IngestionOutcome
    event_id: EventId
    user_id: UserId
    correlation_id: str | None = None
    memory_ids: tuple[MemoryId, ...] = ()
    reason: str | None = None
    duplicate_of_event_id: EventId | None = None


@dataclass(frozen=True)
class IngestionReceipt:
    """Persisted proof that an event was accepted and processed.

    Stored in the dedicated ``ingestion_receipts`` table, separate from
    memory rows. A receipt exists only for events that were ACCEPTED; a
    REJECTED or failed event is never receipted so a corrected retry is
    possible.
    """

    event_id: EventId
    event_type: str
    payload_hash: str
    ingested_at: datetime
    identity_kind: str = "event_id"
    identity_key: str = field(default="")
    user_id: UserId = field(default="")