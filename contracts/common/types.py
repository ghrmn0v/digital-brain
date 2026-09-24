"""Primitive value types shared by every contract.

Conventions
    - Timestamps are timezone-aware UTC datetimes, serialized as ISO 8601.
      Naive datetimes supplied by producers are interpreted as UTC.
    - importance and confidence are floats in [0, 1].
    - provider is an OPEN string: adding a new external connector must never
      force a contract version bump.
"""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

ContractVersion = Literal["v1"]
"""Current contract version (see CONTRACTS.md for the compatibility rules)."""


def _ensure_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"expected datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UtcDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]
"""Timezone-aware UTC datetime. Naive inputs are interpreted as UTC."""

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
"""Producer/model confidence in a value. 0 = unknown, 1 = certain."""

Importance = Annotated[float, Field(ge=0.0, le=1.0)]
"""Importance of a memory to the user's long-term model. Computed by the Brain."""

ProviderName = Annotated[str, Field(min_length=1, max_length=64)]
"""Open vocabulary of the producing system. Known values today:
linkedin, whatsapp, calendar, tasks, jobs, product, fly, system, core, other.
Open by design — new connectors must not break existing contracts."""


class Source(BaseModel):
    """Where a piece of data comes from (system-level provenance)."""

    provider: ProviderName
    component: str | None = Field(default=None, max_length=128)
    version: str | None = Field(default=None, max_length=32)