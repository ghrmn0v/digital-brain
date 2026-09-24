"""Events the Core Brain may emit to consumers (Product UI, Fly behavior).

Only contracts — no processing. Event names come from a FIXED enum for
predictability, and each payload has a documented, open shape. Adding a new
event to the enum is additive (backward compatible).

Payload shapes (documented, not validated — the payload dict stays open):
    memory.created / memory.updated
        {"memory_id", "type", "importance", "confidence", "status"}
    person.created / person.updated
        {"person_id", "name"}
    preference.updated
        {"preference", "value", "source"}
    action.proposed
        {"action_id", "action_type", "requested_permission_level"}
    decision.created
        {"decision_id", "confidence", "action_count"}
    learning.signal.detected
        {"signal", "source", "value"}
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from enum import Enum

from ..common.envelope import EventEnvelope
from ..common.types import UtcDateTime


class BrainEventType(str, Enum):
    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    PERSON_CREATED = "person.created"
    PERSON_UPDATED = "person.updated"
    PREFERENCE_UPDATED = "preference.updated"
    ACTION_PROPOSED = "action.proposed"
    DECISION_CREATED = "decision.created"
    LEARNING_SIGNAL_DETECTED = "learning.signal.detected"


class BrainEvent(EventEnvelope):
    """A typed event emitted by Core Brain to its consumers."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: BrainEventType
    timestamp: UtcDateTime
    related_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)