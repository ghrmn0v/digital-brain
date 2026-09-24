"""Lenient conventions for project metadata stored on Memory.metadata.

The memory contract stores arbitrary ``metadata``; the Context Engine reads a
small, documented set of optional keys so repository-aware retrieval works
without assuming every memory carrys project metadata.

    repository -> ``metadata["repository"]`` or ``metadata["repo"]``
    file       -> ``metadata["file"]`` | ``metadata["file_path"]`` | ``metadata["path"]``
    kind       -> ``metadata["kind"]`` or ``metadata["category"]``

Known kinds drive the Phase 4 category lanes:
    bug findings    ``bug`` | ``bug_finding`` | ``finding`` | ``issue``
    decisions       ``decision`` | ``decisions`` | ``project_decision``
"""

from __future__ import annotations

from contracts.memory.memory import Memory

_REPO_KEYS = ("repository", "repo")
_FILE_KEYS = ("file", "file_path", "path", "current_file")
_KIND_KEYS = ("kind", "category")

_BUG_KINDS = frozenset({"bug", "bug_finding", "finding", "issue"})
_DECISION_KINDS = frozenset({"decision", "decisions", "project_decision"})


def memory_repository(memory: Memory) -> str | None:
    """Optional repository name recorded on a memory, or None."""
    for key in _REPO_KEYS:
        value = memory.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def memory_file(memory: Memory) -> str | None:
    """Optional file path recorded on a memory, or None."""
    for key in _FILE_KEYS:
        value = memory.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def memory_kind(memory: Memory) -> str | None:
    """Optional category/kind recorded on a memory, or None."""
    for key in _KIND_KEYS:
        value = memory.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def is_bug_finding(memory: Memory) -> bool:
    kind = memory_kind(memory)
    return kind is not None and kind in _BUG_KINDS


def is_decision(memory: Memory) -> bool:
    kind = memory_kind(memory)
    return kind is not None and kind in _DECISION_KINDS


def normalize_repository(name: str) -> str:
    """Normalize a repository name for matching (scheme, .git, case, slashes)."""
    value = (name or "").strip().lower()
    if "://" in value:
        value = value.rsplit("://", 1)[-1]
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value.rstrip("/")