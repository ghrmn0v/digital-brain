"""Integration: People Intelligence (Phase 5) + Context Engine (Phase 4).

Verifies that developer preferences and relevant people surfaced by People
Intelligence are the same records the Context Engine assembles, so Phase 6
Reasoning can consume either view consistently.
"""

from __future__ import annotations

import unittest

from core.context import ContextEngine, ContextLimits, LexicalSemanticSearch
from core.context.ranking import Ranker
from core.people import PeopleIntelligence, PreferenceDomain
from core.memory import MemoryService, SqliteMemoryRepository

from tests.context_support import make_dev_context, seed


def build_context(service, dev_context, **engine_kwargs):
    ranker = Ranker()
    search = LexicalSemanticSearch(service, ranker=ranker)
    engine = ContextEngine(
        search,
        limits=ContextLimits(
            top_memories=8,
            top_bug_findings=2,
            top_decisions=2,
            top_preferences=8,
            max_total_memories=20,
            category_min_score=0.0,
        ),
    )
    return engine.build_context(dev_context)


class PeopleContextIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.service = MemoryService(SqliteMemoryRepository(":memory:"))
        self.pi = PeopleIntelligence(self.service, writer=self.service)

    def test_context_developer_preferences_match_people_intelligence(self):
        preference = seed(
            self.service,
            "prefers python for backend",
            user_id="usr_a",
            kind="preference",
            repository="digital-brain",
            importance=0.9,
            extra_metadata={
                "preference_name": "language",
                "preference": "language:language",
                "domain": "language",
            },
        )
        ctx = build_context(
            self.service, make_dev_context(task="python login bug")
        )
        self.assertIn(preference.memory_id, ctx.developer_preferences)
        dev = self.pi.developer_preferences("usr_a")
        self.assertEqual(
            [p.memory_id for p in dev.languages], [preference.memory_id]
        )
        self.assertEqual(
            dev.languages[0].domain, PreferenceDomain.LANGUAGE
        )

    def test_context_relevant_people_agree_with_people_intelligence(self):
        seed(
            self.service,
            "Sadeddin is the Fly owner and python expert",
            user_id="usr_a",
            kind="relationship",
            repository="digital-brain",
            importance=0.9,
            people=("per_sad",),
            extra_metadata={"person_name": "Sadeddin"},
        )
        ctx = build_context(
            self.service, make_dev_context(task="python fly help")
        )
        self.assertIn("per_sad", ctx.relevant_people)
        profile = self.pi.profile("usr_a", "per_sad")
        self.assertEqual(profile.name, "Sadeddin")
        self.assertEqual(len(profile.relationship_facts), 1)
        self.assertEqual(
            [row.person_id for row in self.pi.people_summary("usr_a").people],
            ["per_sad"],
        )

    def test_profile_consistent_with_context_by_memory(self):
        interaction = seed(
            self.service,
            "discussed auth with Sadeddin",
            user_id="usr_a",
            kind="interaction",
            repository="digital-brain",
            people=("per_sad",),
            extra_metadata={"person_name": "Sadeddin"},
        )
        ctx = build_context(
            self.service, make_dev_context(task="discussed auth fix")
        )
        self.assertIn(interaction.memory_id, {m.memory.memory_id for m in ctx.relevant_memories})
        self.assertIn(
            interaction.memory_id,
            {ref.memory_id for ref in self.pi.interactions("usr_a")},
        )


if __name__ == "__main__":
    unittest.main()