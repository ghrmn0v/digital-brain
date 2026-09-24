"""Brain decisions and action proposals.

CRITICAL BOUNDARY — Core Brain PROPOSES, Product (Ayxan) EXECUTES after a
permission check. These models are pure data: a :class:`ProposedAction` carries
intent and parameters, nothing more. There is no execution logic here and there
must never be one attached.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..common.ids import ActionId, DecisionId, EventId, MemoryId, UserId
from ..common.types import (
    Confidence,
    ContractVersion,
    UtcDateTime,
)


class ActionType(str, Enum):
    """Open-additive catalogue of the action kinds the Brain may propose.

    New members are additive and backward compatible (a consumer that does not
    know a type should treat ACTION as "generic").
    """

    SEND_MESSAGE = "send_message"
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    SCHEDULE_EVENT = "schedule_event"
    UPDATE_CALENDAR = "update_calendar"
    UPDATE_PERSON_NOTE = "update_person_note"
    GENERIC = "generic"


class PermissionLevel(str, Enum):
    """How much reach the proposed action would need (requested, not granted).

    The Product permission engine interprets this; the Brain never grants it.
    """

    READ = "read"
    WRITE = "write"
    SEND_MESSAGE = "send_message"
    SCHEDULE = "schedule"
    EXTERNAL = "external"


class ProposedAction(BaseModel):
    """A single action the Brain proposes. NOT an execution request."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    action_id: ActionId
    user_id: UserId
    action_type: ActionType
    reason: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence
    requested_permission_level: PermissionLevel
    created_at: UtcDateTime
    correlation_id: str | None = Field(default=None, max_length=256)


class BrainDecision(BaseModel):
    """The complete decision emitted by the Brain, carrying proposed actions."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    decision_id: DecisionId
    user_id: UserId
    created_at: UtcDateTime
    reason: str
    context_summary: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence
    source_event_ids: list[EventId] = Field(default_factory=list)
    related_memory_ids: list[MemoryId] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    correlation_id: str | None = Field(default=None, max_length=256)