"""Person naming from ingestion + deterministic identity resolution (Phase 5C).

Two guarantees are tested here:

- a connector that names the event subject (without inventing a person id)
  gets a linked, named, mentionable person — resolved by Core, never guessed;
- resolution is deterministic and user-scoped, and an ambiguous name is
  reported instead of merged.
"""

from __future__ import annotations

import unittest

from contracts.brain_events.events import BrainEventType
from contracts.common.types import Source
from contracts.memory.memory import MemoryType

from core.memory.candidate import MemoryCandidate
from core.people import (
    PeopleIntelligence,
    PeopleValidationError,
    mint_person_id,
    normalize_person_name,
)
from core.people.identification import collect_aliases
from core.people.models import PersonResolution
from core.service.api import BrainApi
from core.service.brain_service import build_brain_service

from tests.memory_support import make_service


def service_with_people():
    memory = make_service()
    people = PeopleIntelligence(memory, writer=memory)
    return memory, people


def all_memories(memory, user_id: str):
    from core.memory.filters import MemoryQuery

    return memory.list_memories(MemoryQuery(user_id=user_id, limit=None))


def seed_named(
    memory,
    *,
    user_id: str,
    person_id: str,
    name: str,
    content: str = "Ali works at Acme",
    memory_type: MemoryType = MemoryType.INTERACTION,
) -> str:
    created = memory.create_memory(
        MemoryCandidate(
            content=content,
            user_id=user_id,
            type=memory_type,
            source=Source(provider="whatsapp"),
            related_people=[person_id],
            metadata={"person_name": name},
        )
    )
    return created.memory_id


def event(subject: dict | None, payload: dict, event_id: str = "evt_1") -> dict:
    return {
        "id": event_id,
        "type": "source.whatsapp.message_received",
        "timestamp": "2026-09-25T10:00:00Z",
        "user_id": "usr_ali",
        "source": {"provider": "whatsapp"},
        "occurred_at": "2026-09-25T10:00:00Z",
        "subject": subject,
        "payload": payload,
    }


class ResolvePersonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory, self.people = service_with_people()

    def test_unknown_name_mints_a_deterministic_id_and_one_memory(self) -> None:
        first = self.people.resolve_person("usr_ali", "Ali Ahmadov")
        self.assertIsInstance(first, PersonResolution)
        self.assertTrue(first.created)
        self.assertIsNotNone(first.person_id)
        self.assertIsNotNone(first.memory_id)
        self.assertEqual(first.person_id, mint_person_id("usr_ali", "Ali Ahmadov"))
        self.assertFalse(first.ambiguous)

        second = self.people.resolve_person("usr_ali", "Ali Ahmadov")
        self.assertFalse(second.created)
        self.assertEqual(second.person_id, first.person_id)
        self.assertIsNone(second.memory_id)

    def test_identity_memory_is_traceable_and_durable(self) -> None:
        resolution = self.people.resolve_person("usr_ali", "Ali", aliases=["Aly", "Ali A."])
        memory = self.memory.get_memory("usr_ali", resolution.memory_id)
        self.assertEqual(memory.related_people, [resolution.person_id])
        self.assertEqual(memory.metadata["person_name"], "Ali")
        self.assertEqual(memory.metadata["person_aliases"], ["Aly", "Ali A."])
        self.assertEqual(memory.metadata["kind"], "person_identity")
        self.assertEqual(memory.metadata["durability"], "durable")
        self.assertEqual(
            memory.metadata["person_key"], f"person:{resolution.person_id}:identity"
        )
        self.assertEqual(memory.source.provider, "people")

    def test_name_matching_ignores_case_and_whitespace(self) -> None:
        first = self.people.resolve_person("usr_ali", "Ali Ahmadov")
        again = self.people.resolve_person("usr_ali", "  aLI   ahmadov  ")
        self.assertEqual(again.person_id, first.person_id)
        self.assertFalse(again.created)

    def test_alias_resolves_to_the_same_person(self) -> None:
        first = self.people.resolve_person("usr_ali", "Ali Ahmadov", aliases=["Aly"])
        by_alias = self.people.resolve_person("usr_ali", "Aly")
        self.assertEqual(by_alias.person_id, first.person_id)
        self.assertFalse(by_alias.created)

    def test_token_overlap_is_a_mention_not_an_identity(self) -> None:
        first = self.people.resolve_person("usr_ali", "Ali Ahmadov")
        other = self.people.resolve_person("usr_ali", "Ali Karimov")
        self.assertNotEqual(other.person_id, first.person_id)
        mentions = self.people.identify_people("Ali Ahmadov called", user_id="usr_ali")
        self.assertIn(first.person_id, mentions)
        self.assertIn(other.person_id, mentions)  # "ali" is a shared token

    def test_two_people_with_one_name_are_ambiguous_and_never_merged(self) -> None:
        first = self.people.resolve_person("usr_ali", "Ali")
        seed_named(self.memory, user_id="usr_ali", person_id="per_other_ali", name="Ali")
        before = len(all_memories(self.memory, "usr_ali"))

        resolution = self.people.resolve_person("usr_ali", "Ali")
        self.assertTrue(resolution.ambiguous)
        self.assertIsNone(resolution.person_id)
        self.assertEqual(resolution.candidates, sorted([first.person_id, "per_other_ali"]))
        self.assertGreaterEqual(len(resolution.candidates), 2)
        self.assertEqual(
            len(all_memories(self.memory, "usr_ali")),
            before,
            "an ambiguous name must not write a memory",
        )

        summary = self.people.people_summary("usr_ali")
        self.assertEqual(len(summary.people), 2, "ambiguity must not collapse two people")

    def test_resolution_is_user_scoped(self) -> None:
        ali = self.people.resolve_person("usr_ali", "Ali")
        other = self.people.resolve_person("usr_bəkir", "Ali")
        self.assertNotEqual(ali.person_id, other.person_id)
        self.assertEqual(self.people.resolve_person("usr_ali", "Ali").person_id, ali.person_id)
        self.assertEqual([row.person_id for row in self.people.people_summary("usr_ali").people], [ali.person_id])
        self.assertEqual([row.person_id for row in self.people.people_summary("usr_bəkir").people], [other.person_id])

    def test_identity_record_does_not_inflate_mention_count(self) -> None:
        resolution = self.people.resolve_person("usr_ali", "Ali")
        seed_named(self.memory, user_id="usr_ali", person_id=resolution.person_id, name="Ali")
        summary = self.people.people_summary("usr_ali")
        self.assertEqual(summary.people[0].mention_count, 1)
        self.assertEqual(summary.people[0].name, "Ali")

    def test_normalize_and_alias_bounds(self) -> None:
        self.assertEqual(normalize_person_name("  Ali   Ahmadov "), "ali ahmadov")
        resolution = self.people.resolve_person(
            "usr_ali", "Ali", aliases=["Aly", "  ", "Ali", "A" * 500, 7]
        )
        self.assertEqual(resolution.aliases, ["Aly", "Ali"])

    def test_invalid_input_is_rejected(self) -> None:
        for name in ("", "   ", "x" * 500):
            with self.subTest(name=name):
                with self.assertRaises(PeopleValidationError):
                    self.people.resolve_person("usr_ali", name)

    def test_resolve_requires_a_writer(self) -> None:
        read_only = PeopleIntelligence(self.memory)
        with self.assertRaises(PeopleValidationError):
            read_only.resolve_person("usr_ali", "Ali")

    def test_resolution_model_rejects_inconsistent_state(self) -> None:
        with self.assertRaises(ValueError):
            PersonResolution(user_id="usr_ali", name="Ali", person_id="per_a", ambiguous=True)
        with self.assertRaises(ValueError):
            PersonResolution(user_id="usr_ali", name="Ali")
        with self.assertRaises(ValueError):
            PersonResolution(
                user_id="usr_ali", name="Ali", person_id="per_a", created=True
            )


class ResolvePersonNamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.memory, self.people = service_with_people()

    def test_resolved_person_is_named_and_mentionable(self) -> None:
        resolution = self.people.resolve_person("usr_ali", "Ali Ahmadov")
        seed_named(
            self.memory,
            user_id="usr_ali",
            person_id=resolution.person_id,
            name="Ali Ahmadov",
        )
        summary = self.people.people_summary("usr_ali")
        self.assertEqual(summary.people[0].name, "Ali Ahmadov")
        self.assertEqual(summary.people[0].person_id, resolution.person_id)
        self.assertEqual(
            self.people.identify_people("call Ali Ahmadov later", user_id="usr_ali"),
            [resolution.person_id],
        )
        profile = self.people.profile("usr_ali", resolution.person_id)
        self.assertEqual(profile.name, "Ali Ahmadov")

    def test_aliases_index_collects_every_recorded_name(self) -> None:
        seed_named(self.memory, user_id="usr_ali", person_id="per_x", name="Ali")
        seed_named(self.memory, user_id="usr_ali", person_id="per_x", name="Aly")
        index = collect_aliases(all_memories(self.memory, "usr_ali"))
        self.assertEqual(index["per_x"], frozenset({"Ali", "Aly"}))


class IngestPersonNamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.api = BrainApi(self.service)

    def handle(self, message: dict):
        return self.api.handle(message)

    def test_named_subject_without_person_id_is_resolved_and_linked(self) -> None:
        response = self.handle(
            {
                "id": "r1",
                "method": "ingest",
                "version": "v1",
                "params": {
                    "event": event(
                        {"person_name": "Ali Ahmadov"},
                        {"text": "see you tomorrow"},
                    )
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        memory_ids = response.result.memory_ids
        self.assertEqual(len(memory_ids), 1)

        summary = self.handle(
            {"id": "r2", "method": "people_summary", "version": "v1", "params": {"user_id": "usr_ali"}}
        )
        people = summary.result.people
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].name, "Ali Ahmadov")
        self.assertEqual(people[0].mention_count, 1)

        events = [e.type for e in self.service.emitted]
        self.assertIn(BrainEventType.PERSON_CREATED.value, events)
        person_events = [e for e in self.service.emitted if e.type == BrainEventType.PERSON_CREATED.value]
        self.assertEqual(person_events[0].payload["name"], "Ali Ahmadov")
        self.assertEqual(person_events[0].user_id, "usr_ali")

    def test_explicit_person_id_is_never_re_resolved(self) -> None:
        response = self.handle(
            {
                "id": "r1",
                "method": "ingest",
                "version": "v1",
                "params": {
                    "event": event(
                        {"person_id": "per_connector_1", "person_name": "Ali Ahmadov"},
                        {"text": "hi"},
                        event_id="evt_2",
                    )
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        summary = self.handle(
            {"id": "r2", "method": "people_summary", "version": "v1", "params": {"user_id": "usr_ali"}}
        )
        self.assertEqual(summary.result.people[0].person_id, "per_connector_1")
        self.assertEqual(summary.result.people[0].name, "Ali Ahmadov")
        self.assertNotIn(
            BrainEventType.PERSON_CREATED.value, [e.type for e in self.service.emitted]
        )

    def test_same_name_reuses_the_person_across_events(self) -> None:
        for index in (1, 2):
            self.handle(
                {
                    "id": f"r{index}",
                    "method": "ingest",
                    "version": "v1",
                    "params": {
                        "event": event(
                            {"person_name": "Ali Ahmadov"},
                            {"text": f"message {index}"},
                            event_id=f"evt_{index}",
                        )
                    },
                }
            )
        summary = self.handle(
            {"id": "r3", "method": "people_summary", "version": "v1", "params": {"user_id": "usr_ali"}}
        )
        self.assertEqual(len(summary.result.people), 1)
        self.assertEqual(summary.result.people[0].mention_count, 2)
        created = [
            e for e in self.service.emitted if e.type == BrainEventType.PERSON_CREATED.value
        ]
        self.assertEqual(len(created), 1, "the person is created once, not per event")

    def test_name_without_person_id_and_without_people_keeps_working(self) -> None:
        response = self.handle(
            {
                "id": "r1",
                "method": "ingest",
                "version": "v1",
                "params": {"event": event(None, {"text": "anonymous note"}, event_id="evt_anon")},
            }
        )
        self.assertTrue(response.ok, response.error)
        summary = self.handle(
            {"id": "r2", "method": "people_summary", "version": "v1", "params": {"user_id": "usr_ali"}}
        )
        self.assertEqual(summary.result.people, [])

    def test_ambiguous_name_ingests_but_links_nothing(self) -> None:
        seed = self.service._people.resolve_person("usr_ali", "Ali")
        other = self.service._people.resolve_person("usr_ali", "Ali Karimov")
        # A second, connector-owned person that also answers to "Ali".
        self.service._memory.create_memory(
            MemoryCandidate(
                content="Ali (the other one)",
                user_id="usr_ali",
                type=MemoryType.FACT,
                source=Source(provider="linkedin"),
                related_people=["per_connector_ali"],
                metadata={"person_name": "Ali"},
            )
        )
        response = self.handle(
            {
                "id": "r1",
                "method": "ingest",
                "version": "v1",
                "params": {
                    "event": event(
                        {"person_name": "Ali"}, {"text": "ambiguous"}, event_id="evt_amb"
                    )
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(len(response.result.memory_ids), 1)
        memory = self.service._memory.get_memory("usr_ali", response.result.memory_ids[0])
        self.assertEqual(memory.related_people, [])
        self.assertNotIn("person_name", memory.metadata)
        self.assertNotIn(seed.person_id, memory.related_people)
        self.assertNotIn(other.person_id, memory.related_people)
        self.assertNotIn(
            BrainEventType.PERSON_CREATED.value, [e.type for e in self.service.emitted]
        )


if __name__ == "__main__":
    unittest.main()
