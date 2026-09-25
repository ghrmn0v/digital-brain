"""Transport adapters for the Brain API (Phase 8, Slices 3B and 4).

The transports are transport-only: they never change the API contract, never
alter :class:`BrainApi`, and only adapt the single request-processing entry
point (``BrainApi.handle``) plus the :class:`EventSink` port. IPC and mobile push
can use the same boundary later. See ``docs/stdio-protocol.md``,
``docs/http-transport.md`` and ``docs/websocket-transport.md`` for wire
protocols.
"""

from __future__ import annotations

from .http import (
    API_VERSION,
    HEALTH_PAYLOAD,
    MAX_BODY_BYTES,
    HttpBrainHandler,
    HttpBrainServer,
    HttpBrainTransport,
    http_status_for,
)
from .stdio import (
    EventEnvelope,
    JsonLinesEventSink,
    ResponseEnvelope,
    StdioDaemon,
    default_json_line,
    event_frame,
    response_frame,
)
from .websocket import (
    MAX_MESSAGE_BYTES,
    WebSocketBrainServer,
    WebSocketBrainTransport,
    WebSocketEventRouter,
    WebSocketEventSink,
    WebSocketTransportError,
)

__all__ = [
    "API_VERSION",
    "EventEnvelope",
    "HEALTH_PAYLOAD",
    "HttpBrainHandler",
    "HttpBrainServer",
    "HttpBrainTransport",
    "JsonLinesEventSink",
    "MAX_BODY_BYTES",
    "MAX_MESSAGE_BYTES",
    "ResponseEnvelope",
    "StdioDaemon",
    "WebSocketBrainServer",
    "WebSocketBrainTransport",
    "WebSocketEventRouter",
    "WebSocketEventSink",
    "WebSocketTransportError",
    "default_json_line",
    "event_frame",
    "http_status_for",
    "response_frame",
]