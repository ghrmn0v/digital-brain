"""Brain Events (Phase 6 + Phase 8 Slice 1).

Pure data only. The emitter serializes reasoning/proposals and Brain state
transitions; the pipeline wires reasoning → planning → events for the demo
flow. The EventSink port decouples events from any concrete transport, and the
BrainEventDispatcher routes real state transitions to a sink. No execution
surface exists.
"""

from __future__ import annotations

from .dispatch import BrainEventDispatcher
from .emitter import BrainEventEmitter
from .pipeline import DevModePipeline, DevOutcome
from .sink import CollectingEventSink, EventSink, NullEventSink

__all__ = [
    "BrainEventDispatcher",
    "BrainEventEmitter",
    "CollectingEventSink",
    "DevModePipeline",
    "DevOutcome",
    "EventSink",
    "NullEventSink",
]