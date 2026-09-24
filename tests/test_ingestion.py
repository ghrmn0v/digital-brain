"""Phase 2 ingestion pipeline: validation, dedup, processing, failure, persistence."""

import tempfile
import unittest
from pathlib import Path

from contracts.memory.memory import MemoryType
from core import (
    IngestionOutcome,
    MemoryQuery,
    SqliteEventReceiptRepository,
    build_ingestion,
)

from .ingestion_support import make_event


class TestSchemaValidation(unittest.TestCase):
    def setUp(self):
        self.service = build_ingestion(":memory:")
        self.addCleanup(self.service.close)

    def test_invalid_schema_rejected_and_leaves_no_trace(self):
        bad = make_event(event_id="evt_x", event_type="not.source")
        result = self.service.ingest(bad)
        self.assertEqual(result.outcome, IngestionOutcome.REJECTED)
        self.assertIn("schema", result.reason)

        fixed = self.service.ingest(make_event(event_type="source.linkedin.profile_updated"))
        self.assertEqual(fixed.outcome, IngestionOutcome.ACCEPTED)

    def test_missing_required_fields_rejected(self):
        bad = make_event()
        del bad["id"]
        bad["type"] = "source.whatsapp.message_received"
        result = self.service.ingest(bad)
        self.assertEqual(result.outcome, IngestionOutcome.REJECTED)
        self.assertIn("schema", result.reason)

    def test_extra_fields_forbidden(self):
        bad = make_event(event_type="source.todo.task_created", payload={"description": "x"})
        bad["mystery"] = "nope"
        result = self.service.ingest(bad)
        self.assertEqual(result.outcome, IngestionOutcome.REJECTED)
        self.assertIn("schema", result.reason)

    def test_snake_case_event_types_accepted(self):
        result = self.service.ingest(
            make_event(event_type="source.todo.task_created", payload={"description": "write"})
        )
        self.assertEqual(result.outcome, IngestionOutcome.ACCEPTED)


class TestBusinessValidation(unittest.TestCase):
    def setUp(self):
        self.service = build_ingestion(":memory:")
        self.addCleanup(self.service.close)

    def test_non_json_payload_rejected(self):
        event = make_event(
            event_type="source.linkedin.profile_updated", payload={"nope": {"x"}}
        )
        result = self.service.ingest(event)
        self.assertEqual(result.outcome, IngestionOutcome.REJECTED)
        self.assertIn("JSON", result.reason)

    def test_supported_event_missing_handler_fields_rejected(self):
        result = self.service.ingest(
            make_event(event_type="source.whatsapp.message_received", payload={})
        )
        self.assertEqual(result.outcome, IngestionOutcome.REJECTED)
        self.assertIn("text", result.reason)


class TestMappings(unittest.TestCase):
    def setUp(self):
        self.service = build_ingestion(":memory:")
        self.addCleanup(self.service.close)

    def _ingest(self, **kw):
        result = self.service.ingest(make_event(**kw))
        self.assertEqual(result.outcome, IngestionOutcome.ACCEPTED)
        memories = self.service._memory.list_memories(MemoryQuery(user_id="usr_1"))
        return result, memories

    def test_linkedin_profile_updated_is_fact(self):
        result, memories = self._ingest(
            payload={"full_name": "Aykhan", "section": "experience"}
        )
        self.assertEqual(result.memory_ids, (memories[-1].memory_id,))
        memory = memories[-1]
        self.assertEqual(memory.type, MemoryType.FACT)
        self.assertIn("Aykhan", memory.content)

    def test_linkedin_job_seen_is_fact(self):
        _, memories = self._ingest(
            event_type="source.linkedin.job_seen",
            payload={"company": "Acme", "title": "Engineer"},
        )
        memory = memories[-1]
        self.assertEqual(memory.type, MemoryType.FACT)
        self.assertIn("Acme", memory.content)

    def test_calendar_event_created_is_event(self):
        _, memories = self._ingest(
            event_type="source.calendar.event_created",
            payload={"summary": "Planning", "start": "2026-10-01T09:00:00Z"},
        )
        self.assertEqual(memories[-1].type, MemoryType.EVENT)
        self.assertIn("Planning", memories[-1].content)

    def test_whatsapp_message_received_is_interaction(self):
        _, memories = self._ingest(
            event_type="source.whatsapp.message_received", payload={"text": "Salam!"}
        )
        self.assertEqual(memories[-1].type, MemoryType.INTERACTION)
        self.assertIn("Salam!", memories[-1].content)

    def test_todo_task_created_is_episode(self):
        _, memories = self._ingest(
            event_type="source.todo.task_created", payload={"description": "Ship phase 2"}
        )
        self.assertEqual(memories[-1].type, MemoryType.EPISODE)
        self.assertIn("Ship phase 2", memories[-1].content)

    def test_subject_person_flows_to_related_people(self):
        event = make_event(payload={"full_name": "A"})
        event["subject"] = {"person_id": "per_9"}
        result = self.service.ingest(event)
        self.assertEqual(result.outcome, IngestionOutcome.ACCEPTED)
        memories = self.service._memory.list_memories(MemoryQuery(user_id="usr_1"))
        self.assertEqual(memories[0].related_people, ["per_9"])

    def test_correlation_and_source_traceability(self):
        event = make_event(
            event_type="source.todo.task_created",
            payload={"description": "trace me"},
            correlation_id="corr_42",
            occurred_at="2026-09-24T08:30:00Z",
        )
        result = self.service.ingest(event)
        self.assertEqual(result.outcome, IngestionOutcome.ACCEPTED)
        memory = self.service._memory.list_memories(MemoryQuery(user_id="usr_1"))[0]
        self.assertEqual(memory.related_events, ["evt_1"])
        self.assertEqual(memory.source.provider, "todo")
        self.assertEqual(memory.metadata["source_event_id"], "evt_1")
        self.assertEqual(memory.metadata["correlation_id"], "corr_42")
        self.assertEqual(memory.metadata["occurred_at"], "2026-09-24T08:30:00+00:00")
        self.assertEqual(memory.valid_from.isoformat(), "2026-09-24T08:30:00+00:00")
        self.assertEqual(result.correlation_id, "corr_42")


class TestUnsupportedEvents(unittest.TestCase):
    def setUp(self):
        self.service = build_ingestion(":memory:")
        self.addCleanup(self.service.close)

    def test_unknown_type_accepted_without_memory(self):
        result = self.service.ingest(
            make_event(event_type="source.slack.message_received", payload={"text": "yo"})
        )
        self.assertEqual(result.outcome, IngestionOutcome.ACCEPTED)
        self.assertEqual(result.memory_ids, ())
        memories = self.service._memory.list_memories(MemoryQuery(user_id="usr_1"))
        self.assertEqual(memories, [])


class TestDedup(unittest.TestCase):
    def setUp(self):
        self.service = build_ingestion(":memory:")
        self.addCleanup(self.service.close)

    def _count_memories(self, user_id="usr_1"):
        return len(self.service._memory.list_memories(MemoryQuery(user_id=user_id)))

    def test_same_event_replayed_is_duplicate(self):
        event = make_event(payload={"full_name": "Aykhan"})
        first = self.service.ingest(event)
        second = self.service.ingest(event)
        self.assertEqual(first.outcome, IngestionOutcome.ACCEPTED)
        self.assertEqual(second.outcome, IngestionOutcome.DUPLICATE)
        self.assertEqual(second.duplicate_of_event_id, "evt_1")
        self.assertEqual(self._count_memories(), 1)

    def test_idempotency_key_wins_over_event_id(self):
        first = self.service.ingest(
            make_event(
                event_id="evt_a", event_type="source.todo.task_created",
                payload={"description": "job"}, idempotency_key="op-1",
            )
        )
        second = self.service.ingest(
            make_event(
                event_id="evt_b", event_type="source.todo.task_created",
                payload={"description": "job"}, idempotency_key="op-1",
            )
        )
        self.assertEqual(first.outcome, IngestionOutcome.ACCEPTED)
        self.assertEqual(second.outcome, IngestionOutcome.DUPLICATE)
        self.assertEqual(self._count_memories(), 1)

    def test_distinct_events_are_not_collapsed(self):
        self.service.ingest(make_event(event_id="evt_a"))
        self.service.ingest(make_event(event_id="evt_b"))
        self.assertEqual(self._count_memories(), 2)

    def test_idempotency_key_is_scoped_per_user(self):
        a = self.service.ingest(
            make_event(user_id="usr_a", event_type="source.todo.task_created",
                       payload={"description": "x"}, idempotency_key="op-1")
        )
        b = self.service.ingest(
            make_event(user_id="usr_b", event_type="source.todo.task_created",
                       payload={"description": "x"}, idempotency_key="op-1")
        )
        self.assertEqual(a.outcome, IngestionOutcome.ACCEPTED)
        self.assertEqual(b.outcome, IngestionOutcome.ACCEPTED)
        self.assertEqual(self._count_memories("usr_a"), 1)
        self.assertEqual(self._count_memories("usr_b"), 1)


class TestReceiptPersistence(unittest.TestCase):
    def test_receipts_survive_restart_and_dupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_file = Path(tmp) / "brain.sqlite3"
            service1 = build_ingestion(db_file)
            event = make_event(event_type="source.todo.task_created", payload={"description": "p"})
            self.assertEqual(service1.ingest(event).outcome, IngestionOutcome.ACCEPTED)
            service1.close()

            service2 = build_ingestion(db_file)
            self.addCleanup(service2.close)
            again = service2.ingest(event)
            self.assertEqual(again.outcome, IngestionOutcome.DUPLICATE)
            memories = service2._memory.list_memories(MemoryQuery(user_id="usr_1"))
            self.assertEqual(len(memories), 1)

    def test_receipts_live_in_dedicated_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteEventReceiptRepository(Path(tmp) / "receipts.sqlite3")
            self.addCleanup(repo.close)
            tables = [
                row["name"]
                for row in repo._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            self.assertIn("ingestion_receipts", tables)
            self.assertNotIn("memories", tables)


class TestFailureBehavior(unittest.TestCase):
    def test_rejected_event_never_recorded_so_retry_is_possible(self):
        service = build_ingestion(":memory:")
        self.addCleanup(service.close)
        bad = make_event(event_type="source.todo.task_created", payload={})
        result = service.ingest(bad)
        self.assertEqual(result.outcome, IngestionOutcome.REJECTED)
        # no internal inspection API exists; prove via retry with valid payload
        good = make_event(event_type="source.todo.task_created", payload={"description": "ok"})
        good["idempotency_key"] = "op-retry"
        retry = service.ingest(good)
        self.assertEqual(retry.outcome, IngestionOutcome.ACCEPTED)

    def test_processing_failure_rolls_back_and_retry_succeeds(self):
        service = build_ingestion(":memory:")
        self.addCleanup(service.close)
        event = make_event(event_type="source.todo.task_created", payload={"description": "p"})
        original = service._memory.create_memory

        def boom(candidate):
            raise TypeError("store exploded")

        service._memory.create_memory = boom
        failed = service.ingest(event)
        self.assertEqual(failed.outcome, IngestionOutcome.PROCESSING_FAILED)
        self.assertIn("store exploded", failed.reason)

        service._memory.create_memory = original
        retry = service.ingest(event)
        self.assertEqual(retry.outcome, IngestionOutcome.ACCEPTED)
        memories = service._memory.list_memories(MemoryQuery(user_id="usr_1"))
        self.assertEqual(len(memories), 1)


if __name__ == "__main__":
    unittest.main()