"""Phase 0 contract validation — lightweight, stdlib only.

Run from the repository root:
    python -m unittest discover -s tests -t .
"""

import json
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

import contracts
from contracts import (
    BrainDecision,
    BrainEvent,
    BrainEventType,
    Feedback,
    FeedbackKind,
    FeedbackSource,
    Memory,
    MemoryStatus,
    MemoryType,
    NormalizedSourceEvent,
    Person,
    ProposedAction,
    Source,
    Subject,
)
from contracts.common.types import ContractVersion

NOW = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)


def source(provider: str = "linkedin") -> Source:
    return Source(provider=provider, component="test", version="1")


def sample_source_event(**overrides) -> NormalizedSourceEvent:
    data = dict(
        id="evt_001",
        type="source.linkedin.connection.accepted",
        timestamp=NOW,
        user_id="usr_001",
        source=source(),
        occurred_at=NOW,
        correlation_id="corr-1",
        idempotency_key="ln-abc-123",
        subject=Subject(person_id="per_001", role="connection"),
        payload={"connection": "text"},
    )
    data.update(overrides)
    return NormalizedSourceEvent(**data)


def sample_memory(**overrides) -> Memory:
    data = dict(
        memory_id="mem_001",
        user_id="usr_001",
        type=MemoryType.FACT,
        content="person works at Company B",
        source=source("calendar"),
        confidence=0.95,
        importance=0.8,
        created_at=NOW,
        updated_at=NOW,
        valid_from=NOW,
        related_people=["per_001"],
        metadata={"topic": "employment"},
    )
    data.update(overrides)
    return Memory(**data)


def sample_proposed_action(**overrides) -> ProposedAction:
    data = dict(
        action_id="act_001",
        user_id="usr_001",
        action_type="create_task",
        reason="follow up after meeting",
        parameters={"title": "Send recap", "due": "2026-09-25"},
        confidence=0.7,
        requested_permission_level="write",
        created_at=NOW,
        correlation_id="corr-1",
    )
    data.update(overrides)
    return ProposedAction(**data)


def sample_person(**overrides) -> Person:
    data = dict(
        person_id="per_001",
        user_id="usr_001",
        name="Aykhan",
        emails=["a@example.com"],
        external_identities=[
            {"provider": "linkedin", "external_id": "in-xyz", "verified": True},
            {"provider": "whatsapp", "external_id": "+994-55-000-00-00"},
        ],
        attributes={"job_title": "Engineer"},
        created_at=NOW,
        updated_at=NOW,
    )
    data.update(overrides)
    return Person(**data)


class TestEnvelope(unittest.TestCase):
    def test_required_fields(self):
        with self.assertRaises(ValidationError):
            NormalizedSourceEvent(id="evt_001")  # missing nearly everything

    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValidationError):
            sample_source_event(extra_typo_field=1)

    def test_invalid_version_rejected(self):
        with self.assertRaises(ValidationError):
            sample_source_event(version="v2")
        for model in (sample_memory, sample_proposed_action, sample_person):
            with self.assertRaises(ValidationError):
                model(version="v999")

    def test_unknown_provider_allowed(self):
        ev = sample_source_event()
        ev = ev.model_copy(update={"source": source("some_future_app")})
        self.assertEqual(ev.source.provider, "some_future_app")


class TestIdsAndValues(unittest.TestCase):
    def test_empty_id_rejected(self):
        with self.assertRaises(ValidationError):
            NormalizedSourceEvent(id="", type="source.x.y", timestamp=NOW,
                                  user_id="u", source=source(), occurred_at=NOW)

    def test_confidence_and_importance_bounds(self):
        with self.assertRaises(ValidationError):
            sample_memory(confidence=1.5)
        with self.assertRaises(ValidationError):
            sample_memory(importance=-0.1)
        m = sample_memory(confidence=0.0, importance=1.0)
        self.assertEqual(m.confidence, 0.0)

    def test_naive_datetime_normalized_to_utc(self):
        m = sample_memory(created_at=datetime(2026, 1, 1, 10, 0, 0))
        self.assertIsNotNone(m.created_at.tzinfo)
        self.assertEqual(m.created_at.utcoffset(), timezone.utc.utcoffset(None))

    def test_contract_version_is_stable(self):
        self.assertEqual(ContractVersion.__args__, ("v1",))

    def test_id_aliases_are_exported(self):
        for alias in ("UserId", "PersonId", "EventId", "MemoryId",
                      "DecisionId", "ActionId", "FeedbackId", "EntityId"):
            self.assertTrue(hasattr(contracts, alias), alias)


class TestSourceEvent(unittest.TestCase):
    def test_source_event_type_pattern(self):
        with self.assertRaises(ValidationError):
            sample_source_event(type="connection.accepted")  # missing source.
        with self.assertRaises(ValidationError):
            sample_source_event(type="SOURCE.WHATSAPP.X")  # uppercase
        ok = sample_source_event(type="source.whatsapp.message.received")
        self.assertEqual(ok.type, "source.whatsapp.message.received")

    def test_connector_independent(self):
        for provider, etype in [
            ("linkedin", "source.linkedin.connection.accepted"),
            ("whatsapp", "source.whatsapp.message.received"),
            ("calendar", "source.calendar.event.created"),
            ("tasks", "source.tasks.task.completed"),
            ("jobs", "source.jobs.application.applied"),
        ]:
            ev = sample_source_event(source=Source(provider=provider), type=etype)
            self.assertEqual(ev.source.provider, provider)

    def test_idempotency_fields_present(self):
        ev = sample_source_event()
        self.assertTrue(ev.idempotency_key)
        self.assertTrue(ev.correlation_id)


class TestMemoryContract(unittest.TestCase):
    def test_temporal_split_historical_vs_current(self):
        current = sample_memory(
            memory_id="mem_002",
            content="works at Company B",
            valid_from=NOW,
            valid_until=None,
            status=MemoryStatus.ACTIVE,
        )
        historical = sample_memory(
            memory_id="mem_001",
            content="worked at Company A",
            valid_until=datetime(2026, 3, 1, tzinfo=timezone.utc),
            status=MemoryStatus.SUPERSEDED,
            superseded_by="mem_002",
        )
        self.assertIsNone(current.valid_until)
        self.assertIsNotNone(historical.valid_until)
        self.assertEqual(historical.status, MemoryStatus.SUPERSEDED)
        self.assertEqual(historical.superseded_by, "mem_002")
        dumps = (current.model_dump_json(), historical.model_dump_json())
        self.assertEqual(len(dumps), 2)

    def test_payload_extensible(self):
        m = sample_memory(metadata={"anything": {"deep": [1, 2]}, "n": 3, "b": True})
        self.assertEqual(m.metadata["anything"]["deep"], [1, 2])


class TestPersonContract(unittest.TestCase):
    def test_external_identities_kept_separate(self):
        p = sample_person()
        providers = {i.provider for i in p.external_identities}
        self.assertEqual(providers, {"linkedin", "whatsapp"})

    def test_cannot_put_external_id_in_internal_field(self):
        with self.assertRaises(ValidationError):
            Person(
                person_id="",
                user_id="u",
                name="A",
                created_at=NOW,
                updated_at=NOW,
            )


class TestDecisions(unittest.TestCase):
    def test_proposed_action_is_data_not_execution(self):
        action = sample_proposed_action()
        for forbidden in ("execute", "run", "perform", "status", "executed_at", "result"):
            self.assertFalse(
                hasattr(action, forbidden),
                f"ProposedAction must not carry execution concern: {forbidden}",
            )
        self.assertIsInstance(action, ProposedAction)

    def test_brain_decision_contains_proposals(self):
        decision = BrainDecision(
            decision_id="dec_001",
            user_id="usr_001",
            created_at=NOW,
            reason="meeting follow-up",
            context_summary={"topic": "project sync"},
            confidence=0.7,
            source_event_ids=["evt_001"],
            related_memory_ids=["mem_001"],
            proposed_actions=[sample_proposed_action()],
            correlation_id="corr-1",
        )
        self.assertEqual(len(decision.proposed_actions), 1)
        self.assertEqual(decision.proposed_actions[0].action_type.value, "create_task")


class TestFeedback(unittest.TestCase):
    def test_explicit_user_feedback(self):
        fb = Feedback(
            feedback_id="fdb_001",
            user_id="usr_001",
            source=FeedbackSource.USER,
            kind=FeedbackKind.EXPLICIT,
            target={"memory_id": "mem_001"},
            value=1.0,
            label="helpful",
            created_at=NOW,
        )
        self.assertEqual(fb.kind, FeedbackKind.EXPLICIT)

    def test_fly_reward_signal_is_explicitly_labeled(self):
        fb = Feedback(
            feedback_id="fdb_002",
            user_id="usr_001",
            source=FeedbackSource.FLY,
            kind=FeedbackKind.REWARD,
            target={"action_id": "act_001"},
            value=0.5,
            created_at=NOW,
        )
        self.assertEqual(fb.source, FeedbackSource.FLY)
        self.assertEqual(fb.kind, FeedbackKind.REWARD)
        self.assertNotEqual(fb.kind, FeedbackKind.EXPLICIT)

    def test_feedback_without_target_rejected(self):
        fb = dict(
            feedback_id="fdb_003",
            user_id="usr_001",
            source=FeedbackSource.SYSTEM,
            kind=FeedbackKind.OUTCOME,
            target={},
        )
        with self.assertRaises(ValidationError):
            Feedback(**fb)


class TestBrainEvents(unittest.TestCase):
    def test_event_type_is_fixed_enum(self):
        ev = BrainEvent(
            id="evt-e-1",
            type=BrainEventType.MEMORY_CREATED,
            timestamp=NOW,
            user_id="usr_001",
            source=source("core"),
            related_ids=["mem_001"],
            payload={"memory_id": "mem_001", "type": "fact", "importance": 0.8},
        )
        self.assertEqual(ev.type, "memory.created")

    def test_unknown_event_type_rejected(self):
        with self.assertRaises(ValidationError):
            BrainEvent(
                id="evt-e-2",
                type="memory.archived",
                timestamp=NOW,
                user_id="usr_001",
                source=source("core"),
            )

    def test_all_declared_types_constructable(self):
        for t in BrainEventType:
            ev = BrainEvent(
                id=f"evt-{t.value}",
                type=t,
                timestamp=NOW,
                user_id="usr_001",
                source=source("core"),
            )
            self.assertEqual(ev.type, t)

    def test_action_proposed_event_represents_proposal_only(self):
        ev = BrainEvent(
            id="evt-a-1",
            type=BrainEventType.ACTION_PROPOSED,
            timestamp=NOW,
            user_id="usr_001",
            source=source("core"),
            related_ids=["dec_001", "act_001"],
            payload={"action_id": "act_001", "requested_permission_level": "write"},
        )
        self.assertFalse(hasattr(ev, "executed_at"))


class TestSerialization(unittest.TestCase):
    def test_every_contract_round_trips_json(self):
        cases = [
            sample_source_event(),
            sample_memory(),
            sample_person(),
            sample_proposed_action(),
            Feedback(
                feedback_id="fdb_001",
                user_id="usr_001",
                source=FeedbackSource.USER,
                kind=FeedbackKind.EXPLICIT,
                target={"memory_id": "mem_001"},
                value=1.0,
                created_at=NOW,
            ),
            BrainEvent(
                id="evt-e-1",
                type=BrainEventType.MEMORY_CREATED,
                timestamp=NOW,
                user_id="usr_001",
                source=source("core"),
            ),
        ]
        for model in cases:
            raw = model.model_dump_json()
            self.assertTrue(json.loads(raw) != {})
            reloaded = type(model).model_validate_json(raw)
            self.assertEqual(model.model_dump(), reloaded.model_dump())


if __name__ == "__main__":
    unittest.main()