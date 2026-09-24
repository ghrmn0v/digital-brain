"""Shared fixtures for Memory Engine tests."""

from __future__ import annotations

from datetime import datetime, timezone

from contracts.common.types import Source
from core.memory import MemoryService, SqliteMemoryRepository


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def make_service(path=":memory:", **kwargs) -> MemoryService:
    repo = SqliteMemoryRepository(path)
    return MemoryService(repo, **kwargs)


def linkedin_source() -> Source:
    return Source(provider="linkedin", component="test", version="1")