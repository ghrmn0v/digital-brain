"""Core Brain Ingestion pipeline (Phase 2).

Turns a :class:`~contracts.events.source_event.NormalizedSourceEvent` into an
:class:`IngestionResult`:

    schema validation -> business validation -> dedup -> processing
    -> memory creation -> receipt persistence

All deterministic, no LLM, no brokers. SQLite is the only store.
"""

from .exceptions import (
    EventValidationError,
    IngestionError,
    ReceiptStorageError,
)
from .factory import build_ingestion
from .models import IngestionOutcome, IngestionReceipt, IngestionResult
from .processor import (
    DeterministicEventProcessor,
    EventProcessingError,
    EventProcessor,
    MappingRule,
)
from .receipt_repository import EventReceiptRepository
from .service import IngestionService
from .sqlite_receipt_repository import SqliteEventReceiptRepository

__all__ = [
    "DeterministicEventProcessor",
    "EventProcessingError",
    "EventProcessor",
    "EventReceiptRepository",
    "EventValidationError",
    "IngestionError",
    "IngestionOutcome",
    "IngestionReceipt",
    "IngestionResult",
    "IngestionService",
    "MappingRule",
    "ReceiptStorageError",
    "SqliteEventReceiptRepository",
    "build_ingestion",
]