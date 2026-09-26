"""IngestionService — the small public ingestion API.

    ingest(data: Mapping) -> IngestionResult

Never raises for ordinary input; every path returns a structured outcome.
The pipeline is deterministic and dependency-light (Python + Pydantic +
SQLite only), exactly as the Phase 2 spec requires.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from contracts.events.source_event import NormalizedSourceEvent
from core.memory.temporal import now_utc

from .deduplication import identity_of, payload_hash
from .handlers import find_rule
from .exceptions import EventValidationError
from .models import IngestionOutcome, IngestionReceipt, IngestionResult
from .processor import EventProcessor
from .receipt_repository import EventReceiptRepository
from .transaction import NullTransaction, Transaction
from .validation import accept_event


class IngestionService:
    """Validates, dedupes, processes and persists one source event."""

    def __init__(
        self,
        memory_service: Any,
        receipt_repository: EventReceiptRepository,
        *,
        processor: EventProcessor | None = None,
        transaction: Transaction | None = None,
        finalizer: Callable[[], None] | None = None,
    ) -> None:
        if not callable(getattr(memory_service, "create_memory", None)):
            raise TypeError("memory_service must expose create_memory()")
        if not isinstance(receipt_repository, EventReceiptRepository):
            raise TypeError("receipt_repository must implement EventReceiptRepository")
        self._memory = memory_service
        self._receipts = receipt_repository
        self._processor = processor or _default_processor()
        if not isinstance(self._processor, EventProcessor):
            raise TypeError("processor must implement EventProcessor")
        self._transaction = transaction or NullTransaction()
        self._finalizer = finalizer
        self._closed = False

    # -- the public API ----------------------------------------------------
    def ingest(self, data: Mapping[str, Any]) -> IngestionResult:
        """Validated -> deduped -> processed -> persisted, as one result."""
        try:
            event = accept_event(data)
        except EventValidationError as exc:
            return self._reject(data, exc)

        identity = identity_of(event)
        existing = self._receipts.get(identity)
        if existing is not None:
            return IngestionResult(
                outcome=IngestionOutcome.DUPLICATE,
                event_id=event.id,
                user_id=event.user_id,
                correlation_id=event.correlation_id,
                duplicate_of_event_id=existing.event_id,
            )

        try:
            with self._transaction:
                memory_ids = self._create_memories(event)
                self._receipts.record(
                    identity,
                    IngestionReceipt(
                        event_id=event.id,
                        event_type=event.type,
                        payload_hash=payload_hash(event),
                        ingested_at=now_utc(),
                        identity_kind=identity.kind,
                        identity_key=identity.value,
                        user_id=identity.user_id,
                    ),
                )
        except EventValidationError as exc:
            return self._reject_from_event(event, exc)
        except Exception as exc:
            # Processor/store/logic failures: the worker never reports success
            # for a half-applied event (the transaction rolled back).
            return IngestionResult(
                outcome=IngestionOutcome.PROCESSING_FAILED,
                event_id=event.id,
                user_id=event.user_id,
                correlation_id=event.correlation_id,
                reason=str(exc),
            )

        # An event with no mapping rule is valid and is receipted (dedup must
        # still see it), but nothing was learned from it. Saying only "accepted"
        # makes that indistinguishable from having created a memory, so the
        # reason is stated and the case is logged. The event is deliberately not
        # rejected: it is well-formed, and rejecting it would be a lie about why.
        unmapped = not memory_ids and find_rule(event) is None
        return IngestionResult(
            outcome=IngestionOutcome.ACCEPTED,
            event_id=event.id,
            user_id=event.user_id,
            correlation_id=event.correlation_id,
            memory_ids=tuple(memory_ids),
            reason=(
                f"no mapping rule for {event.type!r}; event receipted but no "
                f"memory was created"
                if unmapped
                else None
            ),
        )

    # -- internals ---------------------------------------------------------
    def _create_memories(self, event: NormalizedSourceEvent) -> list[str]:
        memory_ids: list[str] = []
        for candidate in self._processor.process(event):
            memory = self._memory.create_memory(candidate)
            memory_ids.append(memory.memory_id)
        return memory_ids

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._finalizer is not None:
            self._finalizer()

    # -- result builders ----------------------------------------------------
    @staticmethod
    def _reject(data: Mapping[str, Any], exc: EventValidationError) -> IngestionResult:
        return IngestionResult(
            outcome=IngestionOutcome.REJECTED,
            event_id=_str_field(data, "id", "<invalid>"),
            user_id=_str_field(data, "user_id", "<unknown>"),
            correlation_id=_str_field(data, "correlation_id"),
            reason=str(exc),
        )

    @staticmethod
    def _reject_from_event(event: NormalizedSourceEvent, exc: EventValidationError) -> IngestionResult:
        return IngestionResult(
            outcome=IngestionOutcome.REJECTED,
            event_id=event.id,
            user_id=event.user_id,
            correlation_id=event.correlation_id,
            reason=str(exc),
        )


def _default_processor() -> EventProcessor:
    from .processor import DeterministicEventProcessor

    return DeterministicEventProcessor()


def _str_field(data: Mapping[str, Any], key: str, default: str | None = None) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) and value else default