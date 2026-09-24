"""MemoryService end-to-end: lifecycle, retrieval, user isolation."""

import unittest

from contracts.memory.memory import MemoryStatus, MemoryType
from core.memory import (
    MemoryCandidate,
    MemoryNotFoundError,
    MemoryStatusFilter,
    MemoryQuery,
    MemoryValidationError,
)

from .memory_support import linkedin_source, make_service, utc


def candidate(content, user_id="usr_1", **kw):
    data = dict(content=content, user_id=user_id, source=linkedin_source())
    data.update(kw)
    return MemoryCandidate(**data)


class TestCreateAndGet(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def test_create_and_get_by_id(self):
        created = self.service.create_memory(candidate("met Aykhan in 2024"))
        got = self.service.get_memory("usr_1", created.memory_id)
        self.assertEqual(got.memory_id, created.memory_id)
        self.assertEqual(got.content, "met Aykhan in 2024")
        self.assertEqual(got.type, MemoryType.FACT)
        self.assertEqual(got.status, MemoryStatus.ACTIVE)
        self.assertTrue(got.memory_id.startswith("mem_"))

    def test_explicit_fields_preserved(self):
        created = self.service.create_memory(
            candidate(
                "prefers async comms",
                type=MemoryType.PREFERENCE,
                confidence=0.8,
                importance=0.9,
                memory_id="mem_custom",
                related_people=["per_1"],
                metadata={"kind": "preference"},
            )
        )
        got = self.service.get_memory("usr_1", "mem_custom")
        self.assertEqual(got.confidence, 0.8)
        self.assertEqual(got.importance, 0.9)
        self.assertEqual(got.type, MemoryType.PREFERENCE)
        self.assertEqual(got.related_people, ["per_1"])

    def test_get_unknown_raises(self):
        with self.assertRaises(MemoryNotFoundError):
            self.service.get_memory("usr_1", "mem_missing")

    def test_empty_content_rejected(self):
        with self.assertRaises(MemoryValidationError):
            self.service.create_memory(candidate("   "))


class TestUpdate(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def test_partial_update_merges_metadata(self):
        created = self.service.create_memory(
            candidate("fact", metadata={"topic": "t", "keep": True})
        )
        updated = self.service.update_memory(
            "usr_1", created.memory_id, content="new fact", metadata={"add": 1}
        )
        self.assertEqual(updated.content, "new fact")
        self.assertEqual(updated.metadata["keep"], True)
        self.assertEqual(updated.metadata["add"], 1)
        self.assertGreaterEqual(updated.updated_at, updated.created_at)

    def test_update_nothing_rejected(self):
        created = self.service.create_memory(candidate("x"))
        with self.assertRaises(MemoryValidationError):
            self.service.update_memory("usr_1", created.memory_id)

    def test_update_unknown_raises(self):
        with self.assertRaises(MemoryNotFoundError):
            self.service.update_memory("usr_1", "mem_missing", content="y")


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def test_filter_by_type_and_text(self):
        self.service.create_memory(
            candidate("project kickoff", type=MemoryType.EVENT, metadata={"kind": "event"})
        )
        self.service.create_memory(candidate("project scratch notes"))

        by_type = self.service.list_memories(
            MemoryQuery(user_id="usr_1", memory_type=MemoryType.EVENT)
        )
        self.assertEqual(len(by_type), 1)
        self.assertEqual(by_type[0].type, MemoryType.EVENT)

        by_text = self.service.list_memories(
            MemoryQuery(user_id="usr_1", text="kickoff")
        )
        self.assertEqual(len(by_text), 1)
        self.assertEqual(by_text[0].content, "project kickoff")

    def test_filter_by_person(self):
        self.service.create_memory(
            candidate("about Aykhan", related_people=["per_1"])
        )
        self.service.create_memory(
            candidate("about Zaur", related_people=["per_2"])
        )
        results = self.service.list_memories(
            MemoryQuery(user_id="usr_1", person_id="per_1")
        )
        self.assertEqual([m.content for m in results], ["about Aykhan"])

    def test_filter_by_importance_min(self):
        self.service.create_memory(candidate("dull"))  # 0.5
        self.service.create_memory(
            candidate(
                "important", metadata={"explicit": True, "major_event": True}
            )
        )
        results = self.service.list_memories(
            MemoryQuery(user_id="usr_1", importance_min=0.8)
        )
        self.assertEqual([m.content for m in results], ["important"])

    def test_retrieve_relevant_orders_by_importance(self):
        self.service.create_memory(candidate("low", metadata={"temporary": True}))
        self.service.create_memory(
            candidate("high", metadata={"explicit": True, "major_event": True})
        )
        self.service.create_memory(candidate("medium", metadata={"explicit": True}))
        relevant = self.service.retrieve_relevant_memories("usr_1")
        self.assertEqual(
            [m.content for m in relevant], ["high", "medium", "low"]
        )

    def test_retrieve_relevant_respects_limit_and_active_only(self):
        self.service.create_memory(
            candidate(
                "old job",
                related_people=["per_1"],
                metadata={"topic": "employment"},
                valid_from=utc(2025, 1, 1),
            )
        )
        self.service.create_memory(
            candidate(
                "new job",
                related_people=["per_1"],
                metadata={"topic": "employment"},
                valid_from=utc(2026, 1, 1),
            )
        )
        # "old job" is superseded now
        active = self.service.list_memories(
            MemoryQuery(user_id="usr_1", status=MemoryStatusFilter.ACTIVE)
        )
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].content, "new job")
        self.assertEqual(
            [m.content for m in self.service.retrieve_relevant_memories("usr_1", limit=1)],
            ["new job"],
        )


class TestUserIsolation(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def test_memories_are_strictly_per_user(self):
        a = self.service.create_memory(candidate("mine", user_id="usr_a"))
        self.service.create_memory(candidate("yours", user_id="usr_b"))

        # get cross-user must raise
        with self.assertRaises(MemoryNotFoundError):
            self.service.get_memory("usr_b", a.memory_id)

        # list is scoped
        self.assertEqual(
            len(self.service.list_memories(MemoryQuery(user_id="usr_a"))), 1
        )
        self.assertEqual(
            len(self.service.list_memories(MemoryQuery(user_id="usr_b"))), 1
        )
        self.assertEqual(
            self.service.list_memories(MemoryQuery(user_id="usr_a"))[0].content, "mine"
        )

        # relevance retrieval is scoped
        self.assertEqual(
            [m.content for m in self.service.retrieve_relevant_memories("usr_a")],
            ["mine"],
        )

    def test_cross_user_conflict_does_not_happen(self):
        a = self.service.create_memory(
            candidate(
                "works at A",
                user_id="usr_a",
                related_people=["per_1"],
                metadata={"topic": "employment"},
                valid_from=utc(2026, 3, 1),
            )
        )
        self.service.create_memory(
            candidate(
                "works at B",
                user_id="usr_b",
                related_people=["per_1"],
                metadata={"topic": "employment"},
                valid_from=utc(2026, 3, 2),
            )
        )
        self.assertEqual(
            self.service.get_memory("usr_a", a.memory_id).status,
            MemoryStatus.ACTIVE,
        )


class TestDelete(unittest.TestCase):
    def test_delete(self):
        service = make_service()
        created = service.create_memory(candidate("doomed"))
        self.assertTrue(service.delete_memory("usr_1", created.memory_id))
        self.assertFalse(service.delete_memory("usr_1", created.memory_id))
        with self.assertRaises(MemoryNotFoundError):
            service.get_memory("usr_1", created.memory_id)


if __name__ == "__main__":
    unittest.main()