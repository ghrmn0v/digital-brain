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

Developer Mode events (Phase 6):
    developer.bug_detected
        {"event_id", "repository", "file", "line", "column?", "title",
         "message", "severity", "confidence", "correlation_id",
         "finding_id"}
    developer.fix_proposed
        {"action_id", "affected_file", "affected_lines", "explanation",
         "proposed_change", "confidence", "required_permission_level",
         "correlation_id"}
    developer.test_result
        {"passed", "failed", "skipped", "errors", "summary", "reason",
         "confidence", "correlation_id"}
    developer.review_finding
        {"review_finding_id", "file", "line", "severity", "explanation",
         "confidence", "category", "correlation_id"}
    developer.deploy_proposed
        {"action_id", "environment", "repository", "reason", "test_status",
         "risk_confidence", "required_permission_level", "correlation_id"}
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
    DEVELOPER_BUG_DETECTED = "developer.bug_detected"
    DEVELOPER_FIX_PROPOSED = "developer.fix_proposed"
    DEVELOPER_TEST_RESULT = "developer.test_result"
    DEVELOPER_REVIEW_FINDING = "developer.review_finding"
    DEVELOPER_DEPLOY_PROPOSED = "developer.deploy_proposed"


class BrainEvent(EventEnvelope):
    """A typed event emitted by Core Brain to its consumers."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: BrainEventType
    timestamp: UtcDateTime
    related_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)