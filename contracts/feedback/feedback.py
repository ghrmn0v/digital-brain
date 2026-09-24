"""Feedback contract.

Two dimensions are kept explicit:

- ``source`` = WHERE the feedback came from (USER, PRODUCT, FLY, SYSTEM).
- ``kind``   = WHAT KIND of signal it is (EXPLICIT, IMPLICIT, OUTCOME, REWARD).

Not every feedback is a reward:
- only ``kind == REWARD`` (typically from FLY/SYSTEM) feeds RL reward signals;
- explicit user feedback (USER + EXPLICIT) feeds preference & importance
  learning, not the reward function.
The Brain decides how to use a signal based on the combination of these two
fields — the contract itself only labels them.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..common.ids import (
    ActionId,
    DecisionId,
    EventId,
    FeedbackId,
    MemoryId,
    UserId,
)
from ..common.types import ContractVersion, UtcDateTime


class FeedbackSource(str, Enum):
    USER = "user"
    PRODUCT = "product"
    FLY = "fly"
    SYSTEM = "system"


class FeedbackKind(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    OUTCOME = "outcome"
    REWARD = "reward"


class FeedbackTarget(BaseModel):
    """What the feedback is about. At least one field must be set."""

    model_config = ConfigDict(extra="forbid")

    memory_id: MemoryId | None = None
    decision_id: DecisionId | None = None
    action_id: ActionId | None = None
    event_id: EventId | None = None


class Feedback(BaseModel):
    """A single feedback record."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    feedback_id: FeedbackId
    user_id: UserId
    source: FeedbackSource
    kind: FeedbackKind
    target: FeedbackTarget
    value: float | None = Field(default=None, ge=-1.0, le=1.0)
    label: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=1024)
    created_at: UtcDateTime
    correlation_id: str | None = Field(default=None, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _target_required(self) -> "Feedback":
        if not any(
            field is not None
            for field in (
                self.target.memory_id,
                self.target.decision_id,
                self.target.action_id,
                self.target.event_id,
            )
        ):
            raise ValueError("Feedback.target must reference at least one entity")
        return self