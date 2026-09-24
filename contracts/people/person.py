"""Canonical Brain-owned person representation.

Independent of LinkedIn, WhatsApp, etc. External systems keep their own
identifiers inside ``ExternalIdentity``; the Brain owns ``person_id`` and the
merged/processed profile.

Identity resolution is a LATER phase. This contract only carries the data
needed to eventually resolve and merge identities.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..common.ids import PersonId, UserId
from ..common.types import ContractVersion, ProviderName, UtcDateTime


class ExternalIdentity(BaseModel):
    """An identifier a person has in an external system."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    external_id: str
    profile_url: str | None = None
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Person(BaseModel):
    """A unified person known to the Brain."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    person_id: PersonId
    user_id: UserId
    name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    external_identities: list[ExternalIdentity] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Open profile data, e.g. job_title, employer, location.",
    )
    created_at: UtcDateTime
    updated_at: UtcDateTime
    metadata: dict[str, Any] = Field(default_factory=dict)