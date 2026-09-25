"""Typed, versioned Digital Brain API contracts and schema export.

This package is the platform-independent source consumed by PC, Mobile, Fly,
connectors and external-language generators. It contains no transport or Core
implementation logic. ``core.service.api`` adapts requests to BrainService;
stdio, HTTP and WebSocket are separate transport packages.

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
from .frames import (
    EventEnvelope,
    ResponseEnvelope,
    event_frame,
    response_frame,
)
from .methods import ApiMethod
from .registry import (
    API_CONTRACT_VERSION,
    API_METHOD_REGISTRY,
    API_METHOD_SPECS,
    ApiMethodSpec,
    api_method_names,
    describe_api_methods,
    get_api_method_spec,
)

# Typed per-method request params / result payloads (submodules).
from . import params as params
from . import results as results

__all__ = [
    "API_CONTRACT_VERSION",
    "API_METHOD_REGISTRY",
    "API_METHOD_SPECS",
    "EventEnvelope",
    "ApiError",
    "ApiErrorCode",
    "ApiMethod",
    "ApiMethodSpec",
    "ApiRequest",
    "ApiResponse",
    "ResponseEnvelope",
    "api_method_names",
    "describe_api_methods",
    "error_response",
    "event_frame",
    "get_api_method_spec",
    "ok_response",
    "params",
    "response_frame",
    "results",
]