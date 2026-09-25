"""Typed request parameters for every Brain API method.

These are the wire shapes a client must send. Purposely independent of the Core
Brain modules: the adapter layer (`core.service.api`) maps them to the internal
models. Everything here is `extra="forbid"`, plain pydantic data, and
round-trips through ``model_dump_json()`` / ``model_validate_json()``.

The Developer Mode inputs mirror ``core.understanding.developer.DeveloperContext``
field-for-field so both sides stay honest (the adapter copies, never infers).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.common.ids import PersonId, UserId
from contracts.common.types import ContractVersion, Source
from contracts.events.source_event import NormalizedSourceEvent
from contracts.feedback.feedback import Feedback

TestStatusWire = Literal["passed", "failed", "skipped", "error"]


class PingParams(BaseModel):
    """No parameters — liveness probe."""

    model_config = ConfigDict(extra="forbid")


class DescribeParams(BaseModel):
    """No parameters — returns the method registry + JSON Schemas."""

    model_config = ConfigDict(extra="forbid")


class IngestParams(BaseModel):
    """Ingest a normalized source event (deduped, receipted, memory.created)."""

    model_config = ConfigDict(extra="forbid")

    event: NormalizedSourceEvent
    correlation_id: str | None = Field(default=None, max_length=256)


class RecordFeedbackParams(BaseModel):
    """Feed a Feedback contract into learning (signal.detected + preference.updated)."""

    model_config = ConfigDict(extra="forbid")

    feedback: Feedback
    correlation_id: str | None = Field(default=None, max_length=256)


class RecordPreferenceParams(BaseModel):
    """Write/update one explicit user preference (preference.updated)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)
    domain: str | None = Field(
        default=None,
        max_length=64,
        description="PreferenceDomain value, e.g. 'coding_style'. Coerced by the service.",
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    source: Source | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=256)


class DeveloperFileWire(BaseModel):
    """One file of code context (mirror of ``DeveloperFile``)."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(default="")
    language: str | None = None


class GitSnapshotWire(BaseModel):
    """Repository snapshot at analysis time (mirror of ``GitContext``)."""

    model_config = ConfigDict(extra="forbid")

    branch: str | None = None
    remote: str | None = None
    dirty: bool | None = None
    recent_commits: list[str] = Field(default_factory=list)


class TestResultSnapshotWire(BaseModel):
    """One line of a test run, exactly as reported (mirror of ``TestResultSnapshot``)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=512)
    status: TestStatusWire
    file: str | None = None
    message: str | None = Field(default=None, max_length=4096)


class DeveloperSnapshotWire(BaseModel):
    """Transport-shaped DeveloperContext (mirror of the internal model)."""

    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = "v1"
    user_id: UserId
    repository: str = Field(min_length=1, max_length=512)
    root: str | None = Field(default=None, max_length=1024)
    files: list[DeveloperFileWire] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    current_file: str | None = Field(default=None, max_length=1024)
    current_line: int | None = Field(default=None, ge=1)
    git_context: GitSnapshotWire | None = None
    test_results: list[TestResultSnapshotWire] = Field(default_factory=list)
    user_context: dict[str, Any] = Field(default_factory=dict)


class AnalyzeDeveloperParams(BaseModel):
    """Full Developer Mode pass: Context → Profile → Reasoning → Plan → Events."""

    model_config = ConfigDict(extra="forbid")

    context: DeveloperSnapshotWire
    task: str | None = Field(default=None, max_length=4096)
    ask_deploy: bool = False
    correlation_id: str | None = Field(default=None, max_length=256)


class ReasonParams(BaseModel):
    """Read-only slice: Context → Profile → Reasoning (no planning, no events)."""

    model_config = ConfigDict(extra="forbid")

    context: DeveloperSnapshotWire
    task: str | None = Field(default=None, max_length=4096)


class UnderstandParams(BaseModel):
    """Structured understanding of a corpus (LLM gateway or deterministic fallback)."""

    model_config = ConfigDict(extra="forbid")

    corpus: str = Field(min_length=1, max_length=100_000)
    user_id: str | None = None
    corpus_id: str | None = None


class BuildContextParams(BaseModel):
    """Assemble the bounded Context for a DeveloperContext."""

    model_config = ConfigDict(extra="forbid")

    context: DeveloperSnapshotWire
    task: str | None = Field(default=None, max_length=4096)


class UserParams(BaseModel):
    """User-scoped read (enforced isolation lives in the service)."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId


class PeopleTimelineParams(UserParams):
    """Historical, source-traceable timeline for one known person."""

    model_config = ConfigDict(extra="forbid")

    person_id: PersonId
    limit: int | None = Field(default=None, ge=1, le=200)


class ResolvePersonParams(UserParams):
    """Resolve one person name to a stable id for this user.

    The name is compared exactly (normalized case/whitespace). An unknown name
    yields a new identity; a name already used by two people comes back
    ``ambiguous`` with candidates and writes nothing.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=8)
    correlation_id: str | None = Field(default=None, max_length=256)


class FeedbackHistoryParams(UserParams):
    """Recent feedback history for one user (clockwork ordering)."""

    model_config = ConfigDict(extra="forbid")

    limit: int | None = Field(default=None, ge=1, le=500)

class SearchParams(UserParams):
    """Retrieve this user's own memories by relevance to a question.

    This is the read path the Brain was missing: memory exists, is ranked
    deterministically and is user-isolated, but before this method no canonical
    call could return it. The query is free text; empty text with filters set
    lists by rank alone.

    Isolation is not optional here — ``user_id`` is required, and the service
    refuses to widen it.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=4096)
    keywords: list[str] = Field(default_factory=list, max_length=16)
    memory_type: Literal[
        "fact",
        "episode",
        "interaction",
        "relationship",
        "preference",
        "event",
        "observation",
    ] | None = None
    person_id: PersonId | None = None
    importance_min: float | None = Field(default=None, ge=0.0, le=1.0)
    limit: int = Field(default=10, ge=1, le=50)
    correlation_id: str | None = Field(default=None, max_length=256)


class ChatParams(UserParams):
    """Ask the Brain a question in natural language and get a grounded answer.

    One conversational turn. The Brain retrieves its own memories, preferences,
    people and learned evidence for this user, answers from them, and reports
    exactly which memories it used.

    Two properties are deliberate and load-bearing:

    * the answer is **grounded or absent** — the Brain reports the memories it
      leaned on rather than asserting something it cannot source;
    * a model answer is **never stored**. Learning is only recorded when the
      caller supplies ``target_event_id``, because the Brain never invents a
      traceability id for something it did not observe.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4096)
    session_id: str | None = Field(default=None, max_length=128)
    limit: int = Field(default=8, ge=1, le=32)
    target_event_id: str | None = Field(default=None, max_length=512)
    record_learning: bool = True
    correlation_id: str | None = Field(default=None, max_length=256)
