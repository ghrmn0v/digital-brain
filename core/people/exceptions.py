"""People Intelligence error hierarchy (Phase 5)."""

from __future__ import annotations


class PeopleError(Exception):
    """Base class for all People Intelligence errors."""


class PeopleValidationError(PeopleError):
    """Invalid input to People Intelligence (bad ids, bad limits)."""