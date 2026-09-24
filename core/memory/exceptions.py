"""Memory Engine exception hierarchy."""


class MemoryEngineError(Exception):
    """Base error for the Memory Engine."""


class MemoryValidationError(MemoryEngineError, ValueError):
    """A candidate or input does not satisfy the Memory Engine rules."""


class TemporalValidityError(MemoryValidationError):
    """Temporal fields violate the validity rules (e.g. valid_until < valid_from)."""


class MemoryNotFoundError(MemoryEngineError):
    """The requested memory does not exist for this user."""