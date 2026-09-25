"""EventSink — transport-independent destination for Brain events (Phase 8).

Core Brain never couples to a concrete transport (HTTP, WebSocket, message
bus, Electron IPC, mobile push…). Consumers that want events implement the
:class:`EventSink` port; Core Brain only calls ``emit(event: BrainEvent)``.

Two bundled sinks cover the MVP:

- :class:`NullEventSink` — default. Casts events away when nobody is listening.
- :class:`CollectingEventSink` — in-memory capture for tests, transit buffers
  and future connectors (a future sink may push to REST/Kafka/WebSocket
  without touching any core module).

EventSink is the **consumer port** (Phase 8 Slice 4B — delivery contract). A
``EventSink`` implementation IS a consumer of Brain events; the only contract
it must satisfy is ``emit(event: BrainEvent)``. It must never know anything
about HTTP, WebSocket, mobile SDKs, databases, Redis/Kafka or cloud
infrastructure — transport specifics live in the consumer, not here.

The delivery contract for every consumer receiving events through this port
(fully documented in ``docs/event-delivery.md``):

- **Identity**: ``BrainEvent.id`` is the stable per-emission identity. It is
  minted exactly once when the event is created and never reused, so a
  consumer can recognise a duplicate delivery by comparing ``event.id``.
- **Ordering**: within one synchronous BrainService operation, events are
  delivered to the sink in emission order (one thread, sequential ``emit``
  calls). No global ordering exists across operations, processes or
  transports, and events carry no sequence number.
- **Delivery mode**: in-process, synchronous, **at-most-once, best-effort**.
  Each emission is handed to a sink exactly once or not at all — there is no
  persistence, no retry, no replay and no ack. This is NOT a durable message
  queue.
- **Correlation**: ``correlation_id`` lives in ``payload["correlation_id"]``
  (always present; ``None`` when no correlation was supplied). Envelope
  ``user_id`` + correlation must stay untouched by consumers.
- **Ownership**: ``event.user_id`` is the envelope-level owner; consumers must
  filter by it (``CollectingEventSink.by_user`` does exactly that).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.brain_events.events import BrainEvent, BrainEventType


@runtime_checkable
class EventSink(Protocol):
    """Destination for emitted Brain events (platform-independent).

    This is the consumer port (Slice 4B): a sink receives every event the
    Brain emits, exactly once per emission or not at all (at-most-once,
    best-effort, no retry/replay/durability). Consumers must treat
    ``event.id`` as the deduplication key and ``event.user_id`` as the owner.
    """

    def emit(self, event: BrainEvent) -> None: ...


class NullEventSink:
    """Default sink: validates the event contract and discards it."""

    def emit(self, event: BrainEvent) -> None:
        if not isinstance(event, BrainEvent):
            raise TypeError("EventSink.emit expects a BrainEvent contract")
        # Validated and dropped — no transport attached.


class CollectingEventSink:
    """In-memory sink that captures every emitted event for inspection."""

    def __init__(self) -> None:
        self._emitted: list[BrainEvent] = []

    def emit(self, event: BrainEvent) -> None:
        if not isinstance(event, BrainEvent):
            raise TypeError("EventSink.emit expects a BrainEvent contract")
        self._emitted.append(event)

    @property
    def emitted(self) -> list[BrainEvent]:
        """Snapshot of every event emitted so far (never the live list)."""
        return list(self._emitted)

    def by_user(self, user_id: str) -> list[BrainEvent]:
        """Events owned by one user (no cross-user leakage at the sink)."""
        return [event for event in self._emitted if event.user_id == user_id]

    def by_type(self, event_type: BrainEventType) -> list[BrainEvent]:
        return [event for event in self._emitted if event.type == event_type]

    def clear(self) -> None:
        self._emitted.clear()