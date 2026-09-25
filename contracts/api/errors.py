"""Structured API errors (typed, serializable, transport-independent).

Error codes are a fixed, additive enum. Clients never parse raw exception text:
they branch on ``code`` and treat ``details`` as an open diagnostic payload.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorCode(str, Enum):
    """Additive catalogue of API-level failure codes."""

    BAD_REQUEST = "bad_request"
    """The request is malformed (bad envelope, non-dict params, bad id)."""

    UNKNOWN_METHOD = "unknown_method"
    """The requested method is not implemented by this service instance."""

    VERSION_UNSUPPORTED = "version_unsupported"
    """The request carries a contract version this instance cannot serve."""

    VALIDATION_ERROR = "validation_error"
    """The method is known but the typed params did not validate."""

    NOT_CONFIGURED = "not_configured"
    """The capability backing this method was not configured on the service."""

    INTERNAL_ERROR = "internal_error"
    """An unexpected failure inside the Brain. Details never leak stack traces."""


class ApiError(BaseModel):
    """A single typed error attached to an :class:`ApiResponse`."""

    model_config = ConfigDict(extra="forbid")

    code: ApiErrorCode
    message: str = Field(max_length=2000)
    source: str | None = Field(default=None, max_length=256)
    details: dict[str, Any] = Field(default_factory=dict)