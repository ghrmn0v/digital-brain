"""Shared fixtures for Context Engine (Phase 4) tests."""

from __future__ import annotations

from datetime import datetime, timezone

from contracts.common.types import Source
from contracts.memory.memory import MemoryType

from core.context import LexicalSemanticSearch, SearchError
from core.context.ranking import Ranker
from core.memory import MemoryCandidate, MemoryService, SqliteMemoryRepository
from core.understanding import DeveloperContext

START = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Mutable deterministic clock (MemoryService 'now' + ranking 'now')."""

    def __init__(self, start=START) -> None:
        self.value = start

    def now(self) -> datetime:
        return self.value

    def advance(self, **delta) -> None:
        from datetime import timedelta

        self.value += timedelta(**delta)


def make_service(clock: FakeClock | None = None) -> MemoryService:
    repo = SqliteMemoryRepository(":memory:")
    return MemoryService(repo, now=(clock.now if clock is not None else None))


def make_search(service: MemoryService, clock: FakeClock | None = None) -> LexicalSemanticSearch:
    ranker = Ranker(now=clock.now if clock is not None else None)
    return LexicalSemanticSearch(service, ranker=ranker)


def seed(
    service: MemoryService,
    content: str,
    *,
    user_id: str = "usr_a",
    kind: str | None = None,
    repository: str | None = None,
    file: str | None = None,
    memory_type: MemoryType | None = None,
    importance: float | None = None,
    confidence: float = 0.9,
    people: tuple[str, ...] = (),
    related_events: tuple[str, ...] = (),
    source_event_id: str | None = None,
    provider: str = "product",
    extra_metadata: dict | None = None,
):
    metadata: dict = {}
    if kind is not None:
        metadata["kind"] = kind
    if repository is not None:
        metadata["repository"] = repository
    if file is not None:
        metadata["file"] = file
    if source_event_id is not None:
        metadata["source_event_id"] = source_event_id
    if extra_metadata:
        metadata.update(extra_metadata)
    candidate = MemoryCandidate(
        content=content,
        user_id=user_id,
        type=memory_type,
        source=Source(provider=provider, component="context-test", version="1"),
        confidence=confidence,
        importance=importance,
        related_people=list(people),
        related_events=list(related_events),
        metadata=metadata,
    )
    return service.create_memory(candidate)


def make_dev_context(
    *,
    user_id: str = "usr_a",
    repository: str = "digital-brain",
    current_file: str | None = "core/auth/login.py",
    current_line: int | None = 42,
    task: str | None = None,
    user_context: dict | None = None,
    files=None,
) -> DeveloperContext:
    user_context = dict(user_context or {})
    if task is not None:
        user_context.setdefault("task", task)
    return DeveloperContext(
        user_id=user_id,
        repository=repository,
        current_file=current_file,
        current_line=current_line,
        files=[
            {
                "path": "core/auth/login.py",
                "content": "def get_user():\n    return None\n",
                "language": "python",
            }
        ]
        if files is None
        else files,
        changed_files=["core/auth/login.py"],
        git_context={"branch": "main"},
        user_context=user_context,
    )


class FailingSearch:
    """Search stub that always fails (for failure-behavior tests)."""

    def search(self, query):  # noqa: N805 (stub has no self state)
        raise SearchError("simulated store outage")