"""Tests for People Intelligence (Phase 5): identification, profiles,
relationships, interactions and aggregation."""

from __future__ import annotations

import unittest

from contracts.common.types import Source

from core.memory import MemoryCandidate
from core.people import PeopleIntelligence, PeopleLimits, PeopleValidationError

from tests.memory_support import make_service


def make_intelligence(**kwargs):
    service = make_service()
    return service, PeopleIntelligence(service, writer=service, **kwargs)


def seed(
    service,
    content,
    *,
    user_id="usr_a",
    kind=None,
    memory_type=None,
    person_name=None,
    aliases=None,
    people=(),
    importance=None,
    metadata=None,
    **extra,
):
    meta = dict(metadata or {})
    if kind is not None:
        meta["kind"] = kind
    if person_name is not None:
        meta["person_name"] = person_name
    if aliases is not None:
        meta["person_aliases"] = aliases
    meta.update(extra)
    return service.create_memory(
        MemoryCandidate(
            content=content,
            user_id=user_id,
            type=memory_type,
            source=Source(provider="test", component="people", version="1"),
            importance=importance,
            related_people=list(people),
            metadata=meta,
        )
    )


class PeopleIdentificationTests(unittest.TestCase):
    def test_identify_people_by_name_token(self):
        svc, pi = make_intelligence()
        seed(
            svc, "Ayxan owns the Product layer", kind="relationship",
            person_name="Ayxan", people=("per_1",),
        )
        self.assertEqual(pi.identify_people("look into this", user_id="usr_a"), [])
        self.assertEqual(
            pi.identify_people("can you check ayxan assignment", user_id="usr_a"),
            ["per_1"],
        )

    def test_identify_people_is_case_insensitive_and_uses_aliases(self):
        svc, pi = make_intelligence()
        seed(
            svc, "known alias", kind="fact",
            person_name="Ayxan", aliases=["ghrm0v"],
            people=("per_1",),
        )
        self.assertEqual(
            pi.identify_people("merge as GHRM0V please", user_id="usr_a"),
            ["per_1"],
        )
        self.assertEqual(pi.identify_people("ali is unrelated", user_id="usr_a"), [])

    def test_identify_people_ignores_empty_text_and_other_users(self):
        svc, pi = make_intelligence()
        seed(
            svc, "Ayxan is known", kind="fact",
            person_name="Ayxan", people=("per_1",),
        )
        self.assertEqual(pi.identify_people("", user_id="usr_a"), [])
        self.assertEqual(
            pi.identify_people("Ayxan here", user_id="usr_b"), []
        )

    def test_identify_people_validates_user(self):
        _, pi = make_intelligence()
        with self.assertRaises(PeopleValidationError):
            pi.identify_people("anything", user_id="")


class PersonProfileTests(unittest.TestCase):
    def test_profile_aggregates_person_knowledge(self):
        svc, pi = make_intelligence()
        seed(
            svc, "Ayxan is the Product owner", kind="relationship",
            person_name="Ayxan", people=("per_1",), importance=0.9,
        )
        seed(
            svc, "Reviewed auth PR with Ayxan", kind="interaction",
            people=("per_1",), metadata={"source_event_id": "evt_9"},
        )
        seed(
            svc, "Ayxan prefers split diffs", kind="fact",
            people=("per_1",), importance=0.7,
        )
        profile = pi.profile("usr_a", "per_1")
        self.assertEqual(profile.name, "Ayxan")
        self.assertEqual(profile.mention_count, 3)
        self.assertEqual(len(profile.relationship_facts), 1)
        self.assertEqual(
            profile.relationship_facts[0].statement, "Ayxan is the Product owner"
        )
        self.assertEqual(len(profile.interactions), 1)
        self.assertEqual(profile.interactions[0].source_event_id, "evt_9")
        self.assertEqual(
            [fact.statement for fact in profile.facts],
            ["Ayxan prefers split diffs"],
        )
        self.assertEqual(len(profile.memory_ids), 3)
        self.assertIsNotNone(profile.last_seen)

    def test_profile_unknown_person_is_empty(self):
        svc, pi = make_intelligence()
        profile = pi.profile("usr_a", "per_ghost")
        self.assertEqual(profile.mention_count, 0)
        self.assertIsNone(profile.name)
        self.assertEqual(profile.relationship_facts, [])
        self.assertEqual(profile.interactions, [])
        self.assertEqual(profile.facts, [])
        self.assertEqual(profile.memory_ids, [])

    def test_profile_facts_bounded(self):
        svc, pi = make_intelligence(
            limits=PeopleLimits(max_facts=3, max_relationships=1)
        )
        for i in range(6):
            seed(
                svc, f"fact number {i}", kind="fact",
                people=("per_1",), importance=0.1 * (i + 1),
                metadata={"conflict_key": f"unique_fact_{i}"},
            )
        profile = pi.profile("usr_a", "per_1")
        self.assertEqual(len(profile.facts), 3)
        self.assertEqual(
            [fact.statement for fact in profile.facts],
            ["fact number 5", "fact number 4", "fact number 3"],
        )

    def test_profile_more_important_relationship_wins(self):
        svc, pi = make_intelligence()
        seed(
            svc, "low priority", kind="relationship", people=("per_1",),
            importance=0.2, metadata={"conflict_key": "r1"},
        )
        seed(
            svc, "high priority", kind="relationship", people=("per_1",),
            importance=0.9, metadata={"conflict_key": "r2"},
        )
        profile = pi.profile("usr_a", "per_1")
        self.assertEqual(
            profile.relationship_facts[0].statement, "high priority"
        )

    def test_profile_validates_inputs(self):
        svc, pi = make_intelligence()
        with self.assertRaises(PeopleValidationError):
            pi.profile("", "per_1")
        with self.assertRaises(PeopleValidationError):
            pi.profile("usr_a", "")


class RelationshipInteractionTests(unittest.TestCase):
    def test_relationships_filtered_by_person_and_ranked(self):
        svc, pi = make_intelligence()
        for i, pid in enumerate(("per_a", "per_b", "per_a")):
            seed(
                svc, f"relationship {i}", kind="relationship",
                people=(pid,), importance=0.3 * (i + 1),
                metadata={"conflict_key": f"rel_{i}"},
            )
        all_rows = pi.relationships("usr_a")
        self.assertEqual(len(all_rows), 3)
        self.assertEqual(
            [row.statement for row in all_rows],
            ["relationship 2", "relationship 1", "relationship 0"],
        )
        only_a = pi.relationships("usr_a", person_id="per_a")
        self.assertEqual(len(only_a), 2)
        self.assertTrue(all(row.person_id == "per_a" for row in only_a))

    def test_interactions_reference_history(self):
        svc, pi = make_intelligence()
        seed(
            svc, "pair session with Sadeddin", kind="interaction",
            people=("per_sad",), metadata={"source_event_id": "evt_5"},
        )
        refs = pi.interactions("usr_a")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].person_id, "per_sad")
        self.assertEqual(refs[0].source_event_id, "evt_5")
        self.assertIsNotNone(refs[0].occurred_at)
        self.assertEqual(refs[0].summary, "pair session with Sadeddin")


class PeopleSummaryTests(unittest.TestCase):
    def test_people_summary_ranked_by_mentions(self):
        svc, pi = make_intelligence()
        seed(svc, "mentions a", kind="fact", people=("per_a",), metadata={"conflict_key": "x0"})
        for i in range(3):
            seed(
                svc, "mentions b", kind="fact", people=("per_b",),
                metadata={"conflict_key": f"y{i}"},
            )
        summary = pi.people_summary("usr_a")
        self.assertEqual(
            [row.person_id for row in summary.people],
            ["per_b", "per_a"],
        )
        self.assertEqual(summary.people[0].mention_count, 3)
        self.assertIsNone(summary.people[0].name)

    def test_people_summary_is_user_scoped(self):
        svc, pi = make_intelligence()
        seed(
            svc, "for user a", kind="fact", user_id="usr_a",
            person_name="A", people=("per_1",),
        )
        seed(
            svc, "for user b", kind="fact", user_id="usr_b",
            person_name="B", people=("per_2",),
        )
        self.assertEqual([p.person_id for p in pi.people_summary("usr_a").people], ["per_1"])
        self.assertEqual([p.person_id for p in pi.people_summary("usr_b").people], ["per_2"])


class IsolationTests(unittest.TestCase):
    def test_no_cross_user_leak(self):
        svc, pi = make_intelligence()
        seed(
            svc, "secret relationship A", kind="relationship",
            user_id="usr_a", person_name="A", people=("per_1",),
        )
        seed(
            svc, "secret relationship B", kind="relationship",
            user_id="usr_b", person_name="B", people=("per_2",),
        )
        self.assertEqual(pi.profile("usr_a", "per_1").name, "A")
        self.assertEqual(pi.profile("usr_b", "per_2").name, "B")
        self.assertEqual(pi.profile("usr_a", "per_2").mention_count, 0)
        self.assertEqual(pi.profile("usr_b", "per_1").mention_count, 0)


class DeterminismTests(unittest.TestCase):
    def test_repeated_calls_are_identical(self):
        svc, pi = make_intelligence()
        seed(svc, "rel", kind="relationship", people=("per_1",), importance=0.5)
        seed(svc, "itx", kind="interaction", people=("per_1",))
        first = pi.profile("usr_a", "per_1")
        second = pi.profile("usr_a", "per_1")
        self.assertEqual(first, second)
        self.assertEqual(
            pi.people_summary("usr_a"), pi.people_summary("usr_a")
        )


class ConstructionTests(unittest.TestCase):
    def test_requires_memory_port(self):
        with self.assertRaises(PeopleValidationError):
            PeopleIntelligence(object())
        with self.assertRaises(PeopleValidationError):
            PeopleIntelligence(make_service(), writer=object())


if __name__ == "__main__":
    unittest.main()