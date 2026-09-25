"""Canonical response/event wire-frame envelopes shared by stream transports."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from contracts.brain_events.events import BrainEvent

from .envelope import ApiResponse


class ResponseEnvelope(BaseModel):
    """Outbound wire frame wrapping one typed API response."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["response"] = "response"
    payload: ApiResponse[Any]


class EventEnvelope(BaseModel):
    """Outbound wire frame wrapping one Brain event."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["event"] = "event"
    payload: BrainEvent


def response_frame(response: ApiResponse[Any]) -> dict[str, Any]:
    """Build the JSON-safe response frame for one API response."""
    return ResponseEnvelope(payload=response).model_dump(mode="json")


def event_frame(event: BrainEvent) -> dict[str, Any]:
    """Build the JSON-safe event frame for one Brain event."""
    return EventEnvelope(payload=event).model_dump(mode="json")


__all__ = [
    "EventEnvelope",
    "ResponseEnvelope",
    "event_frame",
    "response_frame",
]
