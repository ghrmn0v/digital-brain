"""Core Brain application-service boundary (Phase 8, Slices 1–3).

``BrainService`` is the first stable, platform-independent entry point above
the Core Brain modules (ingestion, memory, understanding, context, people,
reasoning, action planning, learning, developer events). It coordinates them
through typed Python methods and routes real state transitions to an
:class:`~core.brain_events.sink.EventSink`. No UI/HTTP/device logic lives
here — clients (PC, Mobile, Fly, future connectors) attach through the sink
and the public methods.

Slice 3 adds ``BrainApi`` — the typed, transport-independent client-facing
API coordinator: it maps an ``ApiRequest`` (``contracts.api``) to a
``BrainService`` call and returns a typed ``ApiResponse``. Transports
(stdio JSON-lines daemon, HTTP/WebSocket adapters) feed raw messages into
:meth:`BrainApi.handle`; nothing here listens.

See ``docs/brain-service.md`` and ``docs/brain-api.md``.
"""

from __future__ import annotations

from .api import BrainApi
from .brain_service import BrainService, build_brain_service
from .exceptions import (
    BrainServiceConfigurationError,
    BrainServiceError,
    BrainServiceValidationError,
)

__all__ = [
    "BrainApi",
    "BrainService",
    "BrainServiceConfigurationError",
    "BrainServiceError",
    "BrainServiceValidationError",
    "build_brain_service",
]