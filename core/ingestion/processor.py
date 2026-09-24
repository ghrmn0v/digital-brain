"""Event -> memory-candidate processing.

The processor is a pure port: no I/O, no LLM. It maps an already-validated
event to zero or more memory candidates. Unknown event types are returned as
``[]`` — the pipeline ACCEPTs them and simply records no memory, so a future
mapping can be added without touching past behavior.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from contracts.events.source_event import NormalizedSourceEvent
from core.memory import MemoryCandidate

from .handlers import MappingRule, build_candidate, default_rules


class EventProcessingError(Exception):
    """Raised internally when a handler crashes on an event."""


@runtime_checkable
class EventProcessor(Protocol):
    """Port that turns a validated event into memory candidates."""

    def process(self, event: NormalizedSourceEvent) -> list[MemoryCandidate]: ...


class DeterministicEventProcessor:
    """Registry-driven processor; deterministic by construction."""

    def __init__(
        self, extra_rules: Mapping[tuple[str, str], MappingRule] | None = None
    ) -> None:
        self._rules: dict[tuple[str, str], MappingRule] = default_rules()
        if extra_rules:
            self._rules.update(dict(extra_rules))

    def register(self, provider: str, action: str, rule: MappingRule) -> None:
        # sanity: the rule must describe the key it is registered under
        for existing_key in self._rules:
            if existing_key == (provider, action):
                self._rules[existing_key] = rule
                return
        self._rules[(provider, action)] = rule

    def rules(self) -> dict[tuple[str, str], MappingRule]:
        return dict(self._rules)

    def process(self, event: NormalizedSourceEvent) -> list[MemoryCandidate]:
        rule = self._rules.get(_slice(event))
        if rule is None:
            return []
        try:
            candidate = build_candidate(event, rule)
        except (KeyError, TypeError, ValueError) as exc:
            raise EventProcessingError(
                f"handler {event.type!r} crashed: {exc}"
            ) from exc
        return [candidate] if candidate is not None else []


def _slice(event: NormalizedSourceEvent) -> tuple[str, str]:
    parts = event.type.split(".")
    if len(parts) < 3 or parts[0] != "source":
        return ("", "")
    provider = parts[1]
    action = ".".join(parts[2:])
    return (provider, action)