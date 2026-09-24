"""Deterministic event identity for deduplication.

Two events are "the same dose of reality" when they share a scoped identity
key. Producers that guarantee retries provide an ``idempotency_key``; that
takes precedence. Otherwise the envelope's own ``id`` is used, so replaying
the exact same event is caught but two legitimately different events about the
same thing are NOT collapsed.

Keys are scoped by (identity_kind, composite key, user_id): two users may
submit the same idempotency key without colliding.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from contracts.events.source_event import NormalizedSourceEvent

IDEMPOTENCY_KIND = "idempotency"
EVENT_ID_KIND = "event_id"


@dataclass(frozen=True)
class EventIdentity:
    """Deduplication identity derived from an event, scoped per user."""

    user_id: str
    kind: str
    value: str
    provider: str

    @property
    def key(self) -> str:
        """Composite key ``<provider>:<value>`` for this identity."""
        return f"{self.provider}:{self.value}"

    @property
    def composite(self) -> tuple[str, str, str]:
        """(kind, key, user_id) triple that uniquely scopes a receipt."""
        return (self.kind, self.key, self.user_id)


def identity_of(event: NormalizedSourceEvent) -> EventIdentity:
    """An idempotency key, when present, wins over the envelope id."""
    provider = event.source.provider
    if event.idempotency_key:
        return EventIdentity(
            user_id=event.user_id,
            kind=IDEMPOTENCY_KIND,
            value=event.idempotency_key,
            provider=provider,
        )
    return EventIdentity(
        user_id=event.user_id,
        kind=EVENT_ID_KIND,
        value=event.id,
        provider=provider,
    )


def payload_hash(event: NormalizedSourceEvent) -> str:
    """Deterministic canonical-JSON sha256 of the payload (audit only).

    Assumes the payload already passed JSON-serializability validation.
    """
    canonical = json.dumps(
        event.payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()