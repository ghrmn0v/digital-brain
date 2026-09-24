"""Base envelope for every event exchanged between subsystems.

Core Brain owns this shape. Any event crossing a team boundary has the exact
same outer structure:

    id | type | version | timestamp | user_id | source | payload

So consumers can handle envelope fields uniformly and only branch on ``type``.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ids import EventId, UserId
from .types import ContractVersion, Source, UtcDateTime


class EventEnvelope(BaseModel):
    """The common outer shape of every externally exchanged event."""

    model_config = ConfigDict(extra="forbid")

    id: EventId
    type: str
    version: ContractVersion = "v1"
    timestamp: UtcDateTime
    user_id: UserId
    source: Source
    payload: dict[str, Any] = Field(default_factory=dict)