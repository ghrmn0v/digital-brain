import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

KNOWN_EVENTS = frozenset({
    "important_message",
    "notification",
    "user_message",
    "task_reminder",
    "calendar_event",
    "process_completed",
    "process_failed",
    "warning",
    "app_open",
    "app_idle",
    "unknown",
})

KNOWN_SOURCES = frozenset({
    "whatsapp",
    "core_brain",
    "calendar",
    "tasks",
    "linkedin",
    "app",
    "connectors",
    "unknown",
})

FEEDBACK_TYPES = frozenset({
    "looked",
    "interacted",
    "ignored",
    "dismissed",
    "opened_related",
    "marked_useful",
    "marked_unnecessary",
    "reacted_positive",
    "reacted_negative",
})


@dataclass
class Event:
    id: str
    name: str
    source: str
    priority: float
    person: Optional[Dict[str, Any]]
    context: Dict[str, Any]
    timestamp: float
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Feedback:
    id: str
    behavior_id: str
    feedback: str
    timestamp: float
    context: Dict[str, Any]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


def _clean_name(raw: Dict[str, Any], key: str, allowed: frozenset, default: str) -> str:
    value = raw.get(key, "")
    if isinstance(value, str) and value in allowed:
        return value
    return default


def _safe_priority(raw: Dict[str, Any]) -> float:
    try:
        value = float(raw.get("priority", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


def _safe_timestamp(raw: Dict[str, Any]) -> float:
    value = raw.get("timestamp")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return time.time()
    return time.time()


def _safe_mapping(raw: Dict[str, Any], key: str) -> dict:
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def normalize_event(raw: Dict[str, Any]) -> Event:
    name = _clean_name(raw, "event", KNOWN_EVENTS, "unknown")
    source = _clean_name(raw, "source", KNOWN_SOURCES, "unknown")
    context = dict(_safe_mapping(raw, "context"))
    context.setdefault("urgency", "unknown")
    return Event(
        id=str(raw.get("id") or uuid.uuid4()),
        name=name,
        source=source,
        priority=_safe_priority(raw),
        person=raw.get("person") if isinstance(raw.get("person"), dict) else None,
        context=context,
        timestamp=_safe_timestamp(raw),
        raw=raw,
    )


def is_feedback(raw: Dict[str, Any]) -> bool:
    return raw.get("event") == "fly_feedback"


def normalize_feedback(raw: Dict[str, Any]) -> Feedback:
    feedback = _clean_name(raw, "feedback", FEEDBACK_TYPES, "ignored")
    return Feedback(
        id=str(raw.get("id") or uuid.uuid4()),
        behavior_id=str(raw.get("behavior_id") or "behavior_unknown"),
        feedback=str(feedback),
        timestamp=_safe_timestamp(raw),
        context=dict(_safe_mapping(raw, "context")),
        raw=raw,
    )