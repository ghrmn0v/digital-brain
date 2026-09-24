"""Repository abstraction: DIP with a fake store + SQLite persistence."""

import tempfile
import unittest
from pathlib import Path

from contracts.memory.memory import Memory, MemoryStatus
from core.memory import (
    MemoryCandidate,
    MemoryQuery,
    MemoryStatusFilter,
    MemoryValidationError,
    SqliteMemoryRepository,
)
from core.memory.conflicts import conflict_key
from core.memory.repository import MemoryRepository
from core.memory.service import MemoryService
from core.memory.sqlite_repository import default_db_path
from core.memory.temporal import now_utc

from .memory_support import linkedin_source, utc


class FakeMemoryRepository:
    """Minimal in-memory port implementation used to prove dependency inversion."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Memory] = {}
        self._keys: dict[tuple[str, str], str | None] = {}

    def create(self, memory: Memory) -> Memory:
        key = (memory.user_id, memory.memory_id)
        if key in self._store:
            raise MemoryValidationError("duplicate")
        self._store[key] = memory
        self._keys[key] = conflict_key(memory)
        return memory

    def get(self, user_id: str, memory_id: str) -> Memory | None:
        return self._store.get((user_id, memory_id))

    def update(self, memory: Memory) -> Memory:
        key = (memory.user_id, memory.memory_id)
        if key not in self._store:
            raise MemoryValidationError("missing")
        self._store[key] = memory
        self._keys[key] = conflict_key(memory)
        return memory

    def delete(self, user_id: str, memory_id: str) -> bool:
        return self._store.pop((user_id, memory_id), None) is not None

    def search(self, query: MemoryQuery) -> list[Memory]:
        now = now_utc()
        results = []
        for (user_id, _), memory in self._store.items():
            if user_id != query.user_id:
                continue
            if query.memory_type is not None and memory.type != query.memory_type:
                continue
            if query.conflict_key is not None and self._keys[(user_id, memory.memory_id)] != query.conflict_key:
                continue
            if (
                query.importance_min is not None
                and memory.importance < query.importance_min
            ):
                continue
            if query.source_provider is not None and memory.source.provider != query.source_provider:
                continue
            if query.text is not None and query.text not in memory.content:
                continue
            if query.created_after is not None and memory.created_at < query.created_after:
                continue
            if query.created_before is not None and memory.created_at > query.created_before:
                continue
            if query.person_id is not None and query.person_id not in memory.related_people:
                continue
            active = memory.status == MemoryStatus.ACTIVE and (
                memory.valid_until is None or memory.valid_until > now
            )
            if query.status == MemoryStatusFilter.ACTIVE and not active:
                continue
            if query.status == MemoryStatusFilter.HISTORICAL and active:
                continue
            results.append(memory)
        results.sort(key=lambda m: (m.created_at, m.memory_id), reverse=True)
        if query.limit is not None:
            results = results[query.offset : query.offset + query.limit]
        return results


class TestDependencyInversion(unittest.TestCase):
    def test_service_works_with_any_repository(self):
        repository = FakeMemoryRepository()
        service = MemoryService(repository)

        a = service.create_memory(
            MemoryCandidate(
                content="works at A",
                user_id="usr_1",
                source=linkedin_source(),
                related_people=["per_1"],
                metadata={"topic": "employment"},
                valid_from=utc(2026, 3, 1),
            )
        )
        b = service.create_memory(
            MemoryCandidate(
                content="works at B",
                user_id="usr_1",
                source=linkedin_source(),
                related_people=["per_1"],
                metadata={"topic": "employment"},
                valid_from=utc(2026, 3, 2),
            )
        )
        self.assertEqual(
            service.get_memory("usr_1", a.memory_id).status, MemoryStatus.SUPERSEDED
        )
        self.assertEqual(
            service.get_memory("usr_1", b.memory_id).status, MemoryStatus.ACTIVE
        )
        active = service.list_memories(MemoryQuery(user_id="usr_1"))
        self.assertEqual([m.memory_id for m in active], [b.memory_id])

    def test_repository_protocol_recognizes_fake(self):
        self.assertIsInstance(FakeMemoryRepository(), MemoryRepository)


class TestSqlitePersistence(unittest.TestCase):
    def test_create_duplicate_rejected(self):
        repo = SqliteMemoryRepository(":memory:")
        service = MemoryService(repo)
        created = service.create_memory(
            MemoryCandidate(content="x", user_id="usr_1", source=linkedin_source())
        )
        with self.assertRaises(MemoryValidationError):
            repo.create(created)

    def test_persists_across_reopening(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "brain.sqlite3"
            repo1 = SqliteMemoryRepository(db_file)
            service1 = MemoryService(repo1)
            created = service1.create_memory(
                MemoryCandidate(
                    content="survives restart",
                    user_id="usr_1",
                    source=linkedin_source(),
                    related_people=["per_1", "per_2"],
                )
            )
            repo1.close()

            repo2 = SqliteMemoryRepository(db_file)
            service2 = MemoryService(repo2)
            got = service2.get_memory("usr_1", created.memory_id)
            self.assertEqual(got.content, "survives restart")
            self.assertEqual(got.related_people, ["per_1", "per_2"])
            repo2.close()

    def test_default_db_path_under_repo_data(self):
        self.assertTrue(str(default_db_path()).endswith("data/brain.sqlite3"))


if __name__ == "__main__":
    unittest.main()