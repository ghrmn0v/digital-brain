"""Temporal validity — active vs historical, expiry, validation."""

import unittest

from contracts.memory.memory import MemoryStatus
from core.memory import (
    MemoryCandidate,
    MemoryStatusFilter,
    MemoryQuery,
    TemporalValidityError,
)
from core.memory.service import MemoryService
from core.memory.temporal import is_active, validate_memory_temporal

from .memory_support import linkedin_source, make_service, utc


class TestTemporalValidation(unittest.TestCase):
    def test_valid_until_before_valid_from_rejected(self):
        service = make_service()
        created = service.create_memory(
            MemoryCandidate(
                content="works at A",
                user_id="usr_1",
                source=linkedin_source(),
                valid_from=utc(2026, 3, 1),
            )
        )
        with self.assertRaises(TemporalValidityError):
            service.update_memory(
                "usr_1", created.memory_id, valid_until=utc(2026, 2, 1)
            )

    def test_validate_memory_temporal_direct(self):
        from contracts.memory.memory import Memory
        from contracts.common.types import Source

        good = Memory(
            memory_id="mem_1",
            user_id="usr_1",
            type="fact",
            content="x",
            source=Source(provider="system"),
            confidence=0.5,
            importance=0.5,
            created_at=utc(2026, 1, 1),
            updated_at=utc(2026, 1, 1),
            valid_from=utc(2026, 1, 1),
            valid_until=utc(2026, 1, 2),
        )
        validate_memory_temporal(good)  # no raise

        bad = good.model_copy(update={"valid_until": utc(2025, 12, 31)})
        with self.assertRaises(TemporalValidityError):
            validate_memory_temporal(bad)


class TestActiveAndExpiry(unittest.TestCase):
    def setUp(self):
        self.service = make_service()

    def _create(self, content, metadata=None):
        return self.service.create_memory(
            MemoryCandidate(
                content=content,
                user_id="usr_1",
                source=linkedin_source(),
                valid_from=utc(2026, 3, 1),
                metadata=metadata or {},
            )
        )

    def test_new_memory_is_active(self):
        m = self._create("hello")
        self.assertEqual(m.status, MemoryStatus.ACTIVE)
        self.assertIsNone(m.valid_until)
        self.assertTrue(
            is_active(self.service.get_memory("usr_1", m.memory_id))
        )

    def test_expired_memory_is_no_longer_active(self):
        m = self._create("temporary fact")
        self.service.update_memory("usr_1", m.memory_id, valid_until=utc(2026, 3, 1))
        stored = self.service.get_memory("usr_1", m.memory_id)
        self.assertEqual(stored.status, MemoryStatus.ACTIVE)
        self.assertFalse(is_active(stored, at=utc(2026, 3, 2)))

    def test_active_filter_excludes_expired(self):
        m1 = self._create("still valid")
        m2 = self._create("expired soon")
        self.service.update_memory("usr_1", m2.memory_id, valid_until=utc(2026, 3, 1))

        active = self.service.list_memories(
            MemoryQuery(user_id="usr_1", status=MemoryStatusFilter.ACTIVE)
        )
        ids = {m.memory_id for m in active}
        self.assertIn(m1.memory_id, ids)
        self.assertNotIn(m2.memory_id, ids)

        historical = self.service.list_memories(
            MemoryQuery(user_id="usr_1", status=MemoryStatusFilter.HISTORICAL)
        )
        hist_ids = {m.memory_id for m in historical}
        self.assertIn(m2.memory_id, hist_ids)

    def test_superseded_is_historical(self):
        m = self._create("works at A")
        self.service.supersede_memory("usr_1", m.memory_id, superseded_by="mem_9")
        q = MemoryQuery(
            user_id="usr_1",
            status=MemoryStatusFilter.HISTORICAL,
            text="works at A",
        )
        found = self.service.list_memories(q)
        self.assertTrue(any(x.memory_id == m.memory_id for x in found))


if __name__ == "__main__":
    unittest.main()