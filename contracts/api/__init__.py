"""Digital Brain — client-facing API contracts (Phase 8 Slice 3).

The typed, versioned, platform-independent contract that a client (PC, Mobile,
Fly, future connectors) sends across ANY transport. No implementation logic
lives in this package — the adapter is `core.service.api` and the device-facing
transports come later as EventSink/request implementations.

Versioning: additive changes (new method, new optional field) keep ``v1``;
breaking changes bump the contract version per CONTRACTS.md rules.
"""

from __future__ import annotations

from .envelope import (
    ApiRequest,
    ApiResponse,
    error_response,
    ok_response,
)
from .errors import ApiError, ApiErrorCode
from .methods import ApiMethod

# Typed per-method request params / result payloads (submodules).
from . import params as params
from . import results as results

__all__ = [
    "ApiError",
    "ApiErrorCode",
    "ApiMethod",
    "ApiRequest",
    "ApiResponse",
    "error_response",
    "ok_response",
    "params",
    "results",
]