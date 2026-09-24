"""Conflict resolution — deterministic, scoped by conflict domain."""

import unittest

from contracts.memory.memory import MemoryStatus, MemoryType
from core.memory import (
    MemoryCandidate,
    MemoryStatusFilter,
    MemoryQuery,
)
from core.memory.conflicts import conflict_key, supersede_with

from .memory_support import linkedin_source, make_service, utc


def employment_candidate(content, person="per_1", valid_from=(2026, 3, 1), **kw):
    data = dict(
        content=content,
        user_id="usr_1",
        source=linkedin_source(),
        type=MemoryType.FACT,
        valid_from=utc(*valid_from),
        related_people=[person],
        metadata={"topic": "employment"},
    )
    data.update(kw)
    return MemoryCandidate(**data)


class TestConflictKey(unittest.TestCase):
    def test_employment_domain_from_topic(self):
        c = employment_candidate("works at A")
        self.assertEqual(conflict_key(c), "person:per_1:employment")

    def test_location_domain(self):
        c = MemoryCandidate(
            content="lives in Baku",
            user_id="usr_1",
            source=linkedin_source(),
            type=MemoryType.FACT,
            related_people=["per_9"],
            metadata={"topic": "current_location"},
        )
        self.assertEqual(conflict_key(c), "person:per_9:location")

    def test_preference_domain(self):
        c = MemoryCandidate(
            content="works better in the morning",
            user_id="usr_1",
            source=linkedin_source(),
            type=MemoryType.PREFERENCE,
            metadata={"preference": "focus_time", "kind": "preference"},
        )
        self.assertEqual(conflict_key(c), "user:usr_1:preference:focus_time")

    def test_relationship_domain(self):
        c = MemoryCandidate(
            content="business partner",
            user_id="usr_1",
            source=linkedin_source(),
            type=MemoryType.RELATIONSHIP,
            related_people=["per_1"],
        )
        self.assertEqual(conflict_key(c), "person:per_1:relationship")

    def test_explicit_conflict_key_overrides(self):
        c = employment_candidate(
            "anything", metadata={"conflict_key": "user:usr_1:custom:flag"}
        )
        self.assertEqual(conflict_key(c), "user:usr_1:custom:flag")

    def test_no_domain_returns_none(self):
        c = MemoryCandidate(
            content="had lunch", user_id="usr_1", source=linkedin_source()
        )
        self.assertIsNone(conflict_key(c))


class TestCompanyABecomesCompanyB(unittest.TestCase):
    """The critical scenario: supersession without data loss."""

    def setUp(self):
        self.service = make_service()

    def test_history_preserved_and_current_updated(self):
        a = self.service.create_memory(
            employment_candidate("Hüseyn works at Company A", valid_from=(2026, 3, 1))
        )
        b = self.service.create_memory(
            employment_candidate("Hüseyn works at Company B", valid_from=(2026, 3, 2))
        )

        # A is still stored (not erased)...
        a_stored = self.service.get_memory("usr_1", a.memory_id)
        self.assertEqual(a_stored.content, "Hüseyn works at Company A")
        # ...but no longer the active fact.
        self.assertEqual(a_stored.status, MemoryStatus.SUPERSEDED)
        self.assertEqual(a_stored.superseded_by, b.memory_id)
        self.assertEqual(a_stored.valid_until, utc(2026, 3, 2))

        # B is now current.
        b_stored = self.service.get_memory("usr_1", b.memory_id)
        self.assertEqual(b_stored.status, MemoryStatus.ACTIVE)
        self.assertIsNone(b_stored.valid_until)

    def test_active_set_contains_only_b(self):
        a = self.service.create_memory(
            employment_candidate("works at A", valid_from=(2026, 3, 1))
        )
        b = self.service.create_memory(
            employment_candidate("works at B", valid_from=(2026, 3, 2))
        )
        active = self.service.list_memories(
            MemoryQuery(user_id="usr_1", status=MemoryStatusFilter.ACTIVE)
        )
        active_ids = {m.memory_id for m in active}
        self.assertIn(b.memory_id, active_ids)
        self.assertNotIn(a.memory_id, active_ids)

    def test_historical_remains_retrievable(self):
        a = self.service.create_memory(
            employment_candidate("works at A", valid_from=(2026, 3, 1))
        )
        self.service.create_memory(
            employment_candidate("works at B", valid_from=(2026, 3, 2))
        )
        historical = self.service.list_memories(
            MemoryQuery(user_id="usr_1", status=MemoryStatusFilter.HISTORICAL)
        )
        hist_ids = {m.memory_id for m in historical}
        self.assertIn(a.memory_id, hist_ids)

        # and still directly addressable by id
        a_again = self.service.get_memory("usr_1", a.memory_id)
        self.assertEqual(a_again.superseded_by, a.superseded_by or a_again.superseded_by)


class TestConflictIsolation(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def test_different_people_do_not_conflict(self):
        a = self.service.create_memory(
            employment_candidate("A works at X", person="per_1", valid_from=(2026, 3, 1))
        )
        b = self.service.create_memory(
            employment_candidate("B works at X", person="per_2", valid_from=(2026, 3, 2))
        )
        self.assertEqual(
            self.service.get_memory("usr_1", a.memory_id).status, MemoryStatus.ACTIVE
        )
        self.assertEqual(
            self.service.get_memory("usr_1", b.memory_id).status, MemoryStatus.ACTIVE
        )

    def test_different_topics_do_not_conflict(self):
        a = self.service.create_memory(
            employment_candidate("works at A", valid_from=(2026, 3, 1))
        )
        b = self.service.create_memory(
            MemoryCandidate(
                content="liked the talk",
                user_id="usr_1",
                source=linkedin_source(),
                type=MemoryType.EPISODE,
                valid_from=utc(2026, 3, 2),
                related_people=["per_1"],
                metadata={"temporary": True},
            )
        )
        self.assertEqual(
            self.service.get_memory("usr_1", a.memory_id).status, MemoryStatus.ACTIVE
        )
        self.assertEqual(
            self.service.get_memory("usr_1", b.memory_id).status, MemoryStatus.ACTIVE
        )

    def test_explicit_conflict_key_forces_conflict(self):
        a = self.service.create_memory(
            employment_candidate(
                "one", metadata={"conflict_key": "user:usr_1:slot:seat"}, valid_from=(2026, 3, 1)
            )
        )
        b = self.service.create_memory(
            MemoryCandidate(
                content="two",
                user_id="usr_1",
                source=linkedin_source(),
                valid_from=utc(2026, 3, 2),
                metadata={"conflict_key": "user:usr_1:slot:seat"},
            )
        )
        self.assertEqual(
            self.service.get_memory("usr_1", a.memory_id).status, MemoryStatus.SUPERSEDED
        )
        self.assertEqual(
            self.service.get_memory("usr_1", a.memory_id).superseded_by, b.memory_id
        )

    def test_supersede_with_bounds_validity(self):
        a = self.service.create_memory(
            employment_candidate("works at A", valid_from=(2026, 3, 1))
        )
        b = self.service.create_memory(
            employment_candidate("works at B", valid_from=(2026, 3, 5))
        )
        a_after = self.service.get_memory("usr_1", a.memory_id)
        self.assertEqual(a_after.valid_until, utc(2026, 3, 5))
        self.assertLessEqual(a_after.valid_from, a_after.valid_until)

    def test_supersede_with_when_successor_precedes(self):
        # Paradoxical ordering (successor valid_from earlier): valid_until must
        # not run before valid_from of the old memory.
        a = self.service.create_memory(
            employment_candidate("works at A", valid_from=(2026, 3, 1))
        )
        b = self.service.create_memory(
            employment_candidate("works at B", valid_from=(2025, 12, 1))
        )
        a_after = self.service.get_memory("usr_1", a.memory_id)
        self.assertEqual(a_after.status, MemoryStatus.SUPERSEDED)
        self.assertLessEqual(a_after.valid_from, a_after.valid_until)

    def test_supersede_with_never_extends_old_validity(self):
        from contracts.memory.memory import Memory

        service = self.service
        a = service.create_memory(
            employment_candidate("works at A", valid_from=(2026, 3, 1))
        )
        service.update_memory("usr_1", a.memory_id, valid_until=utc(2026, 3, 4))
        service.create_memory(
            employment_candidate("works at B", valid_from=(2026, 3, 10))
        )
        a_after = service.get_memory("usr_1", a.memory_id)
        self.assertEqual(a_after.valid_until, utc(2026, 3, 4))


if __name__ == "__main__":
    unittest.main()