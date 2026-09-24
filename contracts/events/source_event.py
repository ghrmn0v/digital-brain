"""The canonical event entering Core Brain from the outside world.

Produced by PRODUCT / CONNECTORS (Ayxan) and CONNECTOME / FLY. The contract
does NOT depend on any specific connector: ``source.provider`` names the
originating system and ``payload`` stays open and extensible.
"""

from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..common.envelope import EventEnvelope
from ..common.ids import PersonId
from ..common.types import UtcDateTime

_SourceEventType = Annotated[str, Field(pattern=r"^source\.[a-z0-9]+(\.[a-z0-9]+)+$")]


class Subject(BaseModel):
    """Who/what the event is about, when known at ingestion time."""

    model_config = ConfigDict(extra="forbid")

    person_id: PersonId | None = None
    role: str | None = Field(default=None, max_length=64)


class NormalizedSourceEvent(EventEnvelope):
    """A normalized, connector-independent event the Brain can understand.

    ``type`` naming convention: lowercase, dot-separated, always starting with
    the ``source.`` marker, e.g.
        "source.linkedin.connection.accepted"
        "source.whatsapp.message.received"
        "source.calendar.event.created"

    ``timestamp`` = when the event was recorded / ingested.
    ``occurred_at`` = when the thing happened in the real world (they may differ).
    """

    type: _SourceEventType
    occurred_at: UtcDateTime
    correlation_id: str | None = Field(default=None, max_length=256)
    idempotency_key: str | None = Field(default=None, max_length=256)
    subject: Subject | None = None
    payload: dict[str, Any] = Field(default_factory=dict)