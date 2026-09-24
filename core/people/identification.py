"""Deterministic people identification from memory-derived names.

People are identified by the names/aliases recorded alongside their
``related_people`` entries in Memory Engine records. No fuzzy matching, no
LLM — the Brain can only identify a person whose name reached a memory.
"""

from __future__ import annotations

import re
from typing import Iterable

from contracts.common.ids import PersonId

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> frozenset[str]:
    """Lowercase alphanumeric tokens of a text."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def collect_aliases(
    memories: Iterable[object],
) -> dict[PersonId, frozenset[str]]:
    """Map each referenced person to the names recorded about them.

    Name sources, in priority order (all found are kept as aliases):
      ``metadata["person_name"]``   one canonical name
      ``metadata["person_aliases"]``  any additional known names
      ``metadata["name"]``             fallback generic name slot
    A person is only indexed when a memory references them via
    ``related_people`` — identity always comes from the unified PersonId.
    """
    index: dict[PersonId, set[str]] = {}
    for memory in memories:
        people = getattr(memory, "related_people", None)
        if not people:
            continue
        metadata = getattr(memory, "metadata", {}) or {}
        names: set[str] = set()
        for key in ("person_name", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                names.add(value.strip())
        aliases = metadata.get("person_aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    names.add(alias.strip())
        if not names:
            continue
        for person_id in people:
            index.setdefault(person_id, set()).update(names)
    return {pid: frozenset(names) for pid, names in index.items()}


def identify(
    text: str,
    index: dict[PersonId, frozenset[str]],
) -> list[PersonId]:
    """Return people whose name/alias token appears in ``text`` (sorted)."""
    if not text or not index:
        return []
    tokens = tokenize(text)
    matched: list[PersonId] = []
    for person_id, aliases in index.items():
        alias_tokens: set[str] = set()
        for alias in aliases:
            alias_tokens.update(tokenize(alias))
        if tokens & alias_tokens:
            matched.append(person_id)
    return sorted(matched)