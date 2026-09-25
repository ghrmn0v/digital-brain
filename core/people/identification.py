"""Deterministic people identification from memory-derived names.

People are identified by the names/aliases recorded alongside their
``related_people`` entries in Memory Engine records. No fuzzy matching, no
LLM — the Brain can only identify a person whose name reached a memory.

Identity resolution (:func:`resolve_exact`, :func:`mint_person_id`) follows the
same rule: only an exact, normalized name match reuses an existing person, and
two people sharing a name are reported as ambiguous rather than merged.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable

from contracts.common.ids import PersonId

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

_SLUG_MAX = 40
_HASH_LENGTH = 8


def tokenize(text: str) -> frozenset[str]:
    """Lowercase alphanumeric tokens of a text."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def normalize_person_name(name: str) -> str:
    """Case- and whitespace-insensitive form used for name comparison."""
    return " ".join(name.split()).casefold()


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


def resolve_exact(
    name: str,
    index: dict[PersonId, frozenset[str]],
) -> list[PersonId]:
    """People whose recorded name/alias equals ``name`` exactly (sorted).

    Comparison is normalized (case/whitespace) and never fuzzy: token overlap
    is a *mention* (:func:`identify`), not an identity.
    """
    wanted = normalize_person_name(name)
    if not wanted:
        return []
    return sorted(
        person_id
        for person_id, aliases in index.items()
        if any(normalize_person_name(alias) == wanted for alias in aliases)
    )


def mint_person_id(user_id: str, name: str) -> PersonId:
    """Deterministic person id for an unknown name.

    The same ``(user_id, name)`` always yields the same id, so a re-resolution
    converges instead of forking a second person. The user id is part of the
    digest, which keeps ids scoped per owner by construction. The readable slug
    is cosmetic; the digest suffix carries the uniqueness.
    """
    normalized = normalize_person_name(name)
    slug = _SLUG_RE.sub("_", normalized).strip("_")[:_SLUG_MAX].strip("_")
    digest = hashlib.sha256(f"{user_id}\x00{normalized}".encode("utf-8")).hexdigest()
    suffix = digest[:_HASH_LENGTH]
    return PersonId(f"per_{slug}_{suffix}" if slug else f"per_{suffix}")
