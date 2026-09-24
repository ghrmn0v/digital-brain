"""Two-stage event validation.

1. SCHEMA validation — the event must satisfy the Phase 0
   :class:`NormalizedSourceEvent` contract (shape, types, required fields,
   ``extra="forbid"``). Broken frames are rejected, never repaired.
2. BUSINESS validation — the payload must be usable by the pipeline: it must
   be JSON-serializable (so it can be receipted/hashed) and, for event types
   this pipeline maps to memory, carry the fields the handler needs.

Any failure raises :class:`EventValidationError`, which the service maps to an
``REJECTED`` outcome without storing anything.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from contracts.events.source_event import NormalizedSourceEvent
from pydantic import ValidationError

from .exceptions import EventValidationError
from .handlers import find_rule

_JSON_SEPARATORS = (",", ":")


def parse_source_event(data: Any) -> NormalizedSourceEvent:
    """Schema validation. Raises EventValidationError when the frame is bad."""
    if not isinstance(data, Mapping):
        raise EventValidationError(
            f"event must be a dict-like object, got {type(data).__name__}"
        )
    try:
        return NormalizedSourceEvent.model_validate(dict(data))
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        )
        raise EventValidationError(f"schema invalid: {issues}") from exc


def validate_business(event: NormalizedSourceEvent) -> None:
    """Business validation. Raises EventValidationError when unusable."""
    try:
        json.dumps(
            event.payload,
            sort_keys=True,
            separators=_JSON_SEPARATORS,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise EventValidationError(
            f"payload is not JSON-serializable: {exc}"
        ) from exc

    rule = find_rule(event)
    if rule is None:
        return
    for field_name in rule.required:
        value = event.payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise EventValidationError(
                f"event {event.type!r} requires a non-empty string "
                f"payload field {field_name!r} for processing"
            )


def accept_event(data: Any) -> NormalizedSourceEvent:
    """Full validation: schema then business. Returns a valid event."""
    event = parse_source_event(data)
    validate_business(event)
    return event