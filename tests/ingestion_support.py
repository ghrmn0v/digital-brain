"""Shared fixtures for ingestion tests."""

from __future__ import annotations

from typing import Any


def make_event(
    event_id: str = "evt_1",
    event_type: str = "source.linkedin.profile_updated",
    user_id: str = "usr_1",
    payload: dict[str, Any] | None = None,
    *,
    provider: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    occurred_at: str = "2026-09-24T10:00:00Z",
    timestamp: str = "2026-09-24T10:00:00Z",
) -> dict[str, Any]:
    provider = provider or event_type.split(".")[1]
    event = {
        "id": event_id,
        "type": event_type,
        "version": "v1",
        "timestamp": timestamp,
        "user_id": user_id,
        "source": {"provider": provider, "component": "test", "version": "1"},
        "occurred_at": occurred_at,
        "payload": payload if payload is not None else {},
    }
    if idempotency_key is not None:
        event["idempotency_key"] = idempotency_key
    if correlation_id is not None:
        event["correlation_id"] = correlation_id
    return event