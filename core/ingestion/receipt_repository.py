"""Storage abstraction (port) for ingestion receipts.

Application code depends on this port, never on a concrete store — the same
pattern as the Memory Engine's :class:`~core.memory.MemoryRepository`. Receipts
live in their own table, separate from memory rows, so deduplication state can
survive restarts and be reasoned about independently of memories.

Like memory storage, everything is scoped by user: an identity from user A
never dedupes an event from user B.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .deduplication import EventIdentity
from .models import IngestionReceipt


@runtime_checkable
class EventReceiptRepository(Protocol):
    """Port that any receipt store must implement."""

    def has_seen(self, identity: EventIdentity) -> bool: ...

    def get(self, identity: EventIdentity) -> IngestionReceipt | None: ...

    def record(self, identity: EventIdentity, receipt: IngestionReceipt) -> None: ...