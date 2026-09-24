"""Ingestion pipeline exception hierarchy."""


class IngestionError(Exception):
    """Base error for the ingestion pipeline."""


class EventValidationError(IngestionError, ValueError):
    """An event failed schema or business validation and must be REJECTED."""


class ReceiptStorageError(IngestionError):
    """The receipt store failed to read or write a deduplication receipt."""