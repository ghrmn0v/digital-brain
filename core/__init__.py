"""Core Brain implementation.

Phase 1 provides the deterministic Memory Engine. Phase 2 adds the ingestion
pipeline. No LLM, embeddings or semantic/various search yet.
"""

from .ingestion import (
    DeterministicEventProcessor,
    EventProcessingError,
    EventProcessor,
    EventReceiptRepository,
    EventValidationError,
    IngestionError,
    IngestionOutcome,
    IngestionReceipt,
    IngestionResult,
    IngestionService,
    MappingRule,
    ReceiptStorageError,
    SqliteEventReceiptRepository,
    build_ingestion,
)
from .memory import (
    MemoryCandidate,
    MemoryClassifier,
    MemoryEngineError,
    MemoryNotFoundError,
    MemoryQuery,
    MemoryRepository,
    MemoryService,
    MemoryStatusFilter,
    MemoryValidationError,
    SqliteMemoryRepository,
    TemporalValidityError,
)

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
    "MemoryCandidate",
    "MemoryClassifier",
    "MemoryEngineError",
    "MemoryNotFoundError",
    "MemoryQuery",
    "MemoryRepository",
    "MemoryService",
    "MemoryStatusFilter",
    "MemoryValidationError",
    "ReceiptStorageError",
    "SqliteEventReceiptRepository",
    "SqliteMemoryRepository",
    "TemporalValidityError",
    "build_ingestion",
]