"""Service-boundary errors (Phase 8 Slice 1)."""

from __future__ import annotations


class BrainServiceError(Exception):
    """Base error for the application-service boundary."""


class BrainServiceConfigurationError(BrainServiceError):
    """A required capability was not configured on the service."""


class BrainServiceValidationError(BrainServiceError):
    """The service rejected invalid input before any side effect occurred."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause