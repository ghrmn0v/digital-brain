"""Deterministic event-to-memory mappings.

Only structured, verified data flows into memory content — nothing is
interpreted or synthesized. Each :class:`MappingRule` declares, for one
``(provider, action)`` pair, the memory type and the payload fields the
handler needs. Events this pipeline does not map return no rule (the service
ACCEPTs them without writing memory).

Provenance on every produced candidate: the source, the source event id,
timestamps, provider and correlation id are preserved in metadata /
``related_events`` so each memory is traceable back to exactly one event.

When the event names the person it is about (``subject.person_name`` next to a
resolved ``subject.person_id``), the name is recorded as ``metadata
["person_name"]`` so People Intelligence can label and mention that person.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contracts.events.source_event import NormalizedSourceEvent
from contracts.memory.memory import MemoryType
from core.memory import MemoryCandidate

ContentBuilder = Callable[[dict[str, Any]], str | None]


@dataclass(frozen=True)
class MappingRule:
    """Declarative rule mapping a (provider, action) to a memory."""

    provider: str
    action: str
    memory_type: MemoryType
    build: ContentBuilder
    required: tuple[str, ...] = ()


def _subject_people(event: NormalizedSourceEvent) -> list[str]:
    if event.subject is not None and event.subject.person_id:
        return [event.subject.person_id]
    return []


def _subject_person_name(event: NormalizedSourceEvent) -> str | None:
    """The connector's name for the referenced person, when it gave one.

    A name is only meaningful next to a person id — ``collect_aliases`` ignores
    names on memories that reference nobody, and a bare name must never imply an
    identity Core did not resolve.
    """
    subject = event.subject
    if subject is None or not subject.person_id:
        return None
    name = subject.person_name
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _candidate(
    event: NormalizedSourceEvent,
    *,
    content: str,
    memory_type: MemoryType,
    related_people: list[str],
) -> MemoryCandidate:
    metadata: dict[str, Any] = {
        "source_event_id": event.id,
        "source_event_timestamp": event.timestamp.isoformat(),
        "occurred_at": event.occurred_at.isoformat(),
        "provider": event.source.provider,
        "event_type": event.type,
    }
    if event.correlation_id is not None:
        metadata["correlation_id"] = event.correlation_id
    person_name = _subject_person_name(event)
    if person_name is not None:
        metadata["person_name"] = person_name
    return MemoryCandidate(
        content=content,
        user_id=event.user_id,
        type=memory_type,
        source=event.source,
        valid_from=event.occurred_at,
        related_people=related_people,
        related_events=[event.id],
        metadata=metadata,
    )


def linkedin_profile_updated(payload: dict[str, Any]) -> str | None:
    parts = ["Linkedin profile updated"]
    name = payload.get("full_name")
    if isinstance(name, str) and name.strip():
        parts.append(f"for {name.strip()}")
    section = payload.get("section")
    if isinstance(section, str) and section.strip():
        parts.append(f"({section.strip()})")
    return " ".join(parts)


def linkedin_job_seen(payload: dict[str, Any]) -> str | None:
    company = payload.get("company")
    title = payload.get("title")
    if isinstance(company, str) and company.strip():
        rest = f" ({title.strip()})" if isinstance(title, str) and title.strip() else ""
        return f"Saw job posting at {company.strip()}{rest}"
    if isinstance(title, str) and title.strip():
        return f"Saw job posting for {title.strip()}"
    return None


def calendar_event_created(payload: dict[str, Any]) -> str | None:
    summary = payload.get("summary")
    if not (isinstance(summary, str) and summary.strip()):
        return None
    start = payload.get("start")
    tail = f" on {start}" if isinstance(start, str) and start.strip() else ""
    return f"Calendar event created: {summary.strip()}{tail}"


def whatsapp_message_received(payload: dict[str, Any]) -> str | None:
    text = payload.get("text")
    if not (isinstance(text, str) and text.strip()):
        return None
    return f"WhatsApp message received: {text.strip()}"


def todo_task_created(payload: dict[str, Any]) -> str | None:
    description = payload.get("description")
    if not (isinstance(description, str) and description.strip()):
        return None
    return f"Task created: {description.strip()}"


_RULES: dict[tuple[str, str], MappingRule] = {
    ("linkedin", "profile_updated"): MappingRule(
        provider="linkedin",
        action="profile_updated",
        memory_type=MemoryType.FACT,
        required=(),
        build=linkedin_profile_updated,
    ),
    ("linkedin", "job_seen"): MappingRule(
        provider="linkedin",
        action="job_seen",
        memory_type=MemoryType.FACT,
        required=("company",),
        build=linkedin_job_seen,
    ),
    ("calendar", "event_created"): MappingRule(
        provider="calendar",
        action="event_created",
        memory_type=MemoryType.EVENT,
        required=("summary",),
        build=calendar_event_created,
    ),
    ("whatsapp", "message_received"): MappingRule(
        provider="whatsapp",
        action="message_received",
        memory_type=MemoryType.INTERACTION,
        required=("text",),
        build=whatsapp_message_received,
    ),
    ("todo", "task_created"): MappingRule(
        provider="todo",
        action="task_created",
        memory_type=MemoryType.EPISODE,
        required=("description",),
        build=todo_task_created,
    ),
}


def default_rules() -> dict[tuple[str, str], MappingRule]:
    """Fresh copy of the built-in mapping registry (single source of truth)."""
    return dict(_RULES)


#: Accepted spellings of an action that map onto a canonical rule.
#:
#: Connectors name the same real-world thing differently — a job posting is
#: "seen" to the Brain, "discovered" or "found" to whoever wrote the connector.
#: Without this table such an event is schema-valid, gets receipted, and
#: silently produces no memory, which is indistinguishable from having learned
#: something. Resolving the synonym here fixes it for every sender instead of
#: asking each one to learn the Brain's internal vocabulary.
#:
#: Keys are ``(provider, alias)``; values are the canonical
#: ``(provider, action)`` present in ``_RULES``.
_ACTION_ALIASES: dict[tuple[str, str], tuple[str, str]] = {
    ("linkedin", "job_discovered"): ("linkedin", "job_seen"),
    ("linkedin", "job_found"): ("linkedin", "job_seen"),
    ("linkedin", "job_viewed"): ("linkedin", "job_seen"),
    ("linkedin", "profile_viewed"): ("linkedin", "profile_updated"),
    ("calendar", "event_created"): ("calendar", "event_created"),
    ("todo", "task_created"): ("todo", "task_created"),
}


def find_rule(event: NormalizedSourceEvent) -> MappingRule | None:
    """Rule for ``source.<provider>.<action...>``, or None if unsupported.

    An exact ``(provider, action)`` match always wins; a known synonym is
    resolved to its canonical rule. Anything else is genuinely unmapped and
    returns None, which the ingestion service reports rather than hiding.
    """
    parts = event.type.split(".")
    if len(parts) < 3 or parts[0] != "source":
        return None
    provider = parts[1]
    action = ".".join(parts[2:])
    key = (provider, action)
    rule = _RULES.get(key)
    if rule is not None:
        return rule
    canonical = _ACTION_ALIASES.get(key)
    if canonical is not None:
        return _RULES.get(canonical)
    return None


def rule_key(event: NormalizedSourceEvent) -> tuple[str, str] | None:
    """The canonical ``(provider, action)`` a rule was found under, if any.

    Lets the caller name the rule that actually matched rather than echoing the
    event's own spelling back.
    """
    rule = find_rule(event)
    if rule is None:
        return None
    return (rule.provider, rule.action)


def build_candidate(event: NormalizedSourceEvent, rule: MappingRule) -> MemoryCandidate | None:
    """Build a candidate for a validated event+rule, or None if not buildable."""
    content = rule.build(event.payload)
    if content is None:
        return None
    return _candidate(
        event,
        content=content,
        memory_type=rule.memory_type,
        related_people=_subject_people(event),
    )