"""Structured Understanding results.

The gateway converts raw provider text into this validated model — arbitrary
LLM output never escapes the module in an unvalidated form. Envelope fields
(provider, fallback_used, user_id, corpus_id) are stamped by the gateway from
trusted inputs and never taken from provider output.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from contracts.common.types import Confidence, ContractVersion


class UnderstandingIntent(str, Enum):
    """What a developer is trying to do, interpreted from the input."""

    UNDERSTAND = "understand"
    EXPLAIN = "explain"
    DEBUG = "debug"
    IMPLEMENT = "implement"
    REVIEW = "review"
    DEPLOY = "deploy"
    OTHER = "other"


_MAX_LIST = 24
_MAX_VALUE_LEN = 256


def clean_tags(values: list[str] | None) -> list[str]:
    """Normalize tag-like lists: coerce, strip, dedupe, cap length."""
    if not values:
        return []
    seen: list[str] = []
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()[: _MAX_VALUE_LEN]
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
        if len(seen) >= _MAX_LIST:
            break
    return seen


class UnderstandingResult(BaseModel):
    """A validated interpretation of some (developer) text/code corpus."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    provider: str = "unknown"
    fallback_used: bool = False
    user_id: str | None = None
    corpus_id: str | None = None

    intent: UnderstandingIntent = UnderstandingIntent.UNDERSTAND
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: Confidence
    summary: str = Field(min_length=1, max_length=2000)
    relevant_code_concepts: list[str] = Field(default_factory=list)

    @field_validator("entities", "topics", "relevant_code_concepts", mode="before")
    @classmethod
    def _clean_tags(cls, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return clean_tags(values)

    @field_validator("summary", mode="before")
    @classmethod
    def _strip_summary(cls, values: Any) -> Any:
        if isinstance(values, str):
            return values.strip()
        return values