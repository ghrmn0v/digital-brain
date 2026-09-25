"""Transport adapters for the Brain API (Phase 8, Slice 3 Part B / Slice 4A).

The transports are transport-only: they never change the API contract, never
alter :class:`BrainApi`, and only adapt the single request-processing entry
point (``BrainApi.handle``) plus the :class:`EventSink` port. Future transports
(WebSocket, IPC, mobile push) are additional request/EventSink adapters built
the same way, with no impact on core modules. See ``docs/stdio-protocol.md``
for the stdio wire protocol and ``docs/http-transport.md`` for the HTTP one.
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

__all__ = [
    "API_VERSION",
    "EventEnvelope",
    "HEALTH_PAYLOAD",
    "HttpBrainHandler",
    "HttpBrainServer",
    "HttpBrainTransport",
    "JsonLinesEventSink",
    "MAX_BODY_BYTES",
    "ResponseEnvelope",
    "StdioDaemon",
    "default_json_line",
    "event_frame",
    "http_status_for",
    "response_frame",
]