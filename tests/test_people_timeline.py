"""Tests for source-traceable People timelines and durability semantics."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contracts.api import ApiErrorCode, ApiMethod
from contracts.common.types import Source
from contracts.memory.memory import MemoryStatus, MemoryType

from core import BrainApi, build_brain_service
from core.memory import MemoryCandidate
from core.people import (
    PeopleIntelligence,
    PeopleLimits,
    PeopleValidationError,
    PersonFactDurability,
)

from tests.memory_support import make_service


def _moment(day: int) -> datetime:
    return datetime(2026, 9, day, tzinfo=timezone.utc)


def _intelligence(**kwargs):
    service = make_service()
    return service, PeopleIntelligence(service, writer=service, **kwargs)


def _seed(
    service,
    content: str,
    *,
    day: int,
    person_id: str = "per_ali",
    user_id: str = "usr_a",
    memory_type: MemoryType = MemoryType.FACT,
    metadata: dict | None = None,
    related_events: list[str] | None = None,
):
    values = dict(metadata or {})
    memory = service if hasattr(service, "create_memory") else service._memory
    return memory.create_memory(
        MemoryCandidate(
            content=content,
            user_id=user_id,
            type=memory_type,
            source=Source(
                provider="linkedin",
                component="profile",
                version="2026-09",
            ),
            valid_from=_moment(day),
            related_people=[person_id],
            related_events=list(related_events or []),
            metadata=values,
        )
    )


class PersonTimelineTests(unittest.TestCase):
    def test_timeline_preserves_superseded_history_in_chronological_order(self):
        service, people = _intelligence()
        old = _seed(
            service,
            "Ali is responsible for the backend",
            day=18,
            memory_type=MemoryType.RELATIONSHIP,
            metadata={"conflict_key": "person:per_ali:employment"},
        )
        new = _seed(
            service,
            "Ali now leads the platform team",
            day=25,
            memory_type=MemoryType.RELATIONSHIP,
            metadata={"conflict_key": "person:per_ali:employment"},
        )
        timeline = people.timeline("usr_a", "per_ali")
        self.assertEqual(timeline.total_entries, 2)
        self.assertEqual(
            [entry.memory_id for entry in timeline.entries],
            [old.memory_id, new.memory_id],
        )
        self.assertEqual(
            [entry.status for entry in timeline.entries],
            [MemoryStatus.SUPERSEDED, MemoryStatus.ACTIVE],
        )
        self.assertEqual(
            [entry.durability for entry in timeline.entries],
            [PersonFactDurability.DURABLE, PersonFactDurability.DURABLE],
        )
        self.assertEqual(people.profile("usr_a", "per_ali").mention_count, 1)

    def test_timeline_entry_keeps_source_event_and_correlation_trace(self):
        service, people = _intelligence()
        _seed(
            service,
            "Ali is a backend engineer",
            day=20,
            metadata={
                "topic": "employment",
                "explicit": True,
                "source_event_id": "evt_linkedin_1",
                "correlation_id": "corr_linkedin_1",
            },
            related_events=["evt_linkedin_1"],
        )
        entry = people.timeline("usr_a", "per_ali").entries[0]
        self.assertEqual(entry.provenance.source.provider, "linkedin")
        self.assertEqual(entry.provenance.source.component, "profile")
        self.assertEqual(entry.provenance.source_event_id, "evt_linkedin_1")
        self.assertEqual(entry.provenance.correlation_id, "corr_linkedin_1")
        self.assertEqual(entry.provenance.related_event_ids, ["evt_linkedin_1"])
        self.assertEqual(entry.provenance.evidence["topic"], "employment")
        self.assertTrue(entry.provenance.evidence["explicit"])

    def test_durability_uses_explicit_metadata_before_inference(self):
        service, people = _intelligence()
        _seed(
            service,
            "Ali was tired today",
            day=21,
            memory_type=MemoryType.OBSERVATION,
            metadata={"temporary": True},
        )
        _seed(
            service,
            "Ali is responsible for the backend",
            day=22,
            memory_type=MemoryType.FACT,
            metadata={"topic": "responsibility"},
        )
        _seed(
            service,
            "Ali may prefer async reviews",
            day=23,
            memory_type=MemoryType.FACT,
        )
        _seed(
            service,
            "Ali is a teammate",
            day=24,
            memory_type=MemoryType.RELATIONSHIP,
        )
        entries = people.timeline("usr_a", "per_ali").entries
        self.assertEqual(
            [entry.durability for entry in entries],
            [
                PersonFactDurability.TEMPORARY,
                PersonFactDurability.DURABLE,
                PersonFactDurability.UNSPECIFIED,
                PersonFactDurability.DURABLE,
            ],
        )

    def test_timeline_is_bounded_and_marks_truncation(self):
        service, people = _intelligence(
            limits=PeopleLimits(max_timeline_entries=2, scan_limit=10)
        )
        for day in range(1, 5):
            _seed(service, f"fact {day}", day=day)
        timeline = people.timeline("usr_a", "per_ali")
        self.assertEqual(len(timeline.entries), 2)
        self.assertEqual(timeline.total_entries, 4)
        self.assertTrue(timeline.truncated)
        self.assertFalse(timeline.scan_truncated)
        self.assertTrue(timeline.person_known)

    def test_scan_limit_is_reported_separately_from_output_limit(self):
        service, people = _intelligence(
            limits=PeopleLimits(max_timeline_entries=2, scan_limit=2)
        )
        for day in range(1, 5):
            _seed(service, f"fact {day}", day=day)
        timeline = people.timeline("usr_a", "per_ali")
        self.assertEqual(timeline.total_entries, 2)
        self.assertEqual(len(timeline.entries), 2)
        self.assertFalse(timeline.truncated)
        self.assertTrue(timeline.scan_truncated)

    def test_unknown_person_is_explicitly_reported(self):
        _service, people = _intelligence()
        timeline = people.timeline("usr_a", "per_unknown")
        self.assertEqual(timeline.entries, [])
        self.assertFalse(timeline.person_known)
        self.assertFalse(timeline.truncated)
        self.assertFalse(timeline.scan_truncated)

    def test_durability_topic_precedes_generic_observation_type(self):
        service, people = _intelligence()
        _seed(
            service,
            "A structured employment observation",
            day=20,
            memory_type=MemoryType.OBSERVATION,
            metadata={"topic": "employment"},
        )
        self.assertEqual(
            people.timeline("usr_a", "per_ali").entries[0].durability,
            PersonFactDurability.DURABLE,
        )

    def test_oversized_provenance_and_statement_are_flagged(self):
        service, people = _intelligence()
        _seed(
            service,
            "x" * 2500,
            day=20,
            metadata={
                "source_event_id": "e" * 600,
                "correlation_id": "c" * 300,
            },
        )
        entry = people.timeline("usr_a", "per_ali").entries[0]
        self.assertTrue(entry.statement_truncated)
        self.assertEqual(len(entry.statement), 2000)
        self.assertTrue(entry.provenance.source_event_id_truncated)
        self.assertTrue(entry.provenance.correlation_id_truncated)
        self.assertEqual(len(entry.provenance.source_event_id), 512)
        self.assertEqual(len(entry.provenance.correlation_id), 256)
        self.assertEqual(len(entry.provenance.evidence["source_event_id"]), 512)
        self.assertEqual(len(entry.provenance.evidence["correlation_id"]), 300)

    def test_repeated_timeline_reads_are_deterministic(self):
        service, people = _intelligence()
        for day in (1, 2, 3):
            _seed(service, f"fact {day}", day=day)
        self.assertEqual(
            people.timeline("usr_a", "per_ali"),
            people.timeline("usr_a", "per_ali"),
        )

    def test_invalid_timeline_limits_fail_early(self):
        for value in (0, -1, 201):
            with self.assertRaises(ValueError):
                PeopleLimits(max_timeline_entries=value)
        with self.assertRaises(PeopleValidationError):
            _intelligence()[1].timeline("usr_a", "p" * 513)

    def test_timeline_is_user_scoped(self):
        service, people = _intelligence()
        _seed(service, "A fact for user A", day=1, user_id="usr_a")
        _seed(service, "A fact for user B", day=2, user_id="usr_b")
        self.assertEqual(len(people.timeline("usr_a", "per_ali").entries), 1)
        self.assertEqual(len(people.timeline("usr_b", "per_ali").entries), 1)
        self.assertEqual(
            people.timeline("usr_a", "per_ali").entries[0].statement,
            "A fact for user A",
        )

    def test_timeline_validates_inputs(self):
        service, people = _intelligence()
        with self.assertRaises(PeopleValidationError):
            people.timeline("", "per_ali")
        with self.assertRaises(PeopleValidationError):
            people.timeline("usr_a", "")
        with self.assertRaises(PeopleValidationError):
            people.timeline("usr_a", "per_ali", limit=0)


class PeopleTimelineApiTests(unittest.TestCase):
    def test_api_returns_typed_timeline(self):
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        _seed(service, "Ali is a teammate", day=20)
        response = BrainApi(service).handle(
            {
                "id": "timeline-1",
                "method": "people_timeline",
                "params": {"user_id": "usr_a", "person_id": "per_ali"},
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.method, ApiMethod.PEOPLE_TIMELINE)
        self.assertEqual(response.result.person_id, "per_ali")
        self.assertEqual(response.result.total_entries, 1)
        self.assertEqual(
            response.result.entries[0].provenance.provider,
            "linkedin",
        )

    def test_api_timeline_is_user_scoped(self):
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        _seed(service, "A private timeline", day=20, user_id="usr_a")
        _seed(service, "B private timeline", day=21, user_id="usr_b")
        api = BrainApi(service)
        first = api.handle(
            {
                "id": "a",
                "method": "people_timeline",
                "params": {"user_id": "usr_a", "person_id": "per_ali"},
            }
        )
        second = api.handle(
            {
                "id": "b",
                "method": "people_timeline",
                "params": {"user_id": "usr_b", "person_id": "per_ali"},
            }
        )
        self.assertEqual(first.result.entries[0].statement, "A private timeline")
        self.assertEqual(second.result.entries[0].statement, "B private timeline")

    def test_api_timeline_rejects_invalid_limit(self):
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        response = BrainApi(service).handle(
            {
                "id": "timeline-2",
                "method": "people_timeline",
                "params": {
                    "user_id": "usr_a",
                    "person_id": "per_ali",
                    "limit": 0,
                },
            }
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)


if __name__ == "__main__":
    unittest.main()
