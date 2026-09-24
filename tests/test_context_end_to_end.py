"""Phase 4 — deterministic end-to-end Developer Mode context test (no LLM)."""

import unittest

from core.context import ContextEngine, ContextStatus
from core.memory import MemoryQuery

from .context_support import FakeClock, make_dev_context, make_search, make_service, seed


class TestEndToEnd(unittest.TestCase):
    def runTest(self):
        clock = FakeClock()
        service = make_service(clock)

        # 1. Memories for user A across several repositories.
        bug_a_file = seed(
            service,
            "user is missing -> user.email throws null reference (fixed before via guard)",
            user_id="usr_a",
            repository="digital-brain",
            file="core/auth/login.py",
            kind="bug_finding",
            importance=0.95,
            source_event_id="evt_bug_1",
        )
        seed(
            service,
            "login flow decided to use guard clauses for nullable user",
            user_id="usr_a",
            repository="digital-brain",
            kind="decision",
            importance=0.8,
        )
        unrelated_other_repo = seed(
            service,
            "billing service uses a python script for monthly invoice generation",
            user_id="usr_a",
            repository="other-repo",
            importance=0.9,
        )
        # 2. A developer preference for user A (relevant to the current failure).
        pref = seed(
            service,
            "when a function fails, Ayxan prefers to check for a missing user first",
            user_id="usr_a",
            kind="preference",
            importance=0.85,
        )
        # 3. User B has an identical finding in the SAME repository/file.
        seed(
            service,
            "user is missing -> user.email throws null reference (fixed before via guard)",
            user_id="usr_b",
            repository="digital-brain",
            file="core/auth/login.py",
            kind="bug_finding",
            importance=1.0,
        )

        clock.advance(days=1)
        search = make_search(service, clock)
        engine = ContextEngine(search, now=clock.now)

        # 5. DeveloperContext for repository A / current file.
        dev = make_dev_context(
            user_id="usr_a",
            repository="digital-brain",
            current_file="core/auth/login.py",
            current_line=42,
            task="Find why this function fails when user is missing",
        )

        # 6. Build the Context (deterministic, no live LLM).
        ctx = engine.build_context(dev)
        ctx_again = engine.build_context(dev)

        # 10. Bounded.
        self.assertLessEqual(len(ctx.relevant_memories), 16)
        self.assertEqual(ctx.status, ContextStatus.FULL)

        ranked_ids = [r.memory.memory_id for r in ctx.relevant_memories]

        # 9. User B memory is never returned.
        b_memories = {
            memory.memory_id
            for memory in service.list_memories(MemoryQuery(user_id="usr_b"))
        }
        self.assertFalse(set(ranked_ids) & b_memories)

        # 7. Most relevant repository+file memory is prioritized.
        self.assertEqual(ranked_ids[0], bug_a_file.memory_id)
        self.assertEqual(ctx.previous_bug_findings, [bug_a_file.memory_id])
        self.assertEqual(ctx.relevant_memories[0].repository_match, "exact")
        self.assertEqual(ctx.relevant_memories[0].file_match, "exact")
        self.assertIn("category", ctx.relevant_memories[0].matched_fields)

        # 8. Unrelated-repository memory is lower priority OR excluded (spec).
        self.assertNotEqual(ranked_ids[0], unrelated_other_repo.memory_id)
        if unrelated_other_repo.memory_id in ranked_ids:
            other_idx = ranked_ids.index(unrelated_other_repo.memory_id)
            self.assertGreater(other_idx, 0)  # same-repo finding ranks above it
            self.assertEqual(ranked_ids[0], bug_a_file.memory_id)

        # preference lane surfaced.
        self.assertIn(pref.memory_id, ctx.developer_preferences)

        # Determinism: identical ranking across two independent builds.
        self.assertEqual(
            [r.model_dump() for r in ctx.relevant_memories],
            [r.model_dump() for r in ctx_again.relevant_memories],
        )
        # Current context preserved.
        self.assertEqual(ctx.current_file, "core/auth/login.py")
        self.assertEqual(ctx.current_line, 42)
        self.assertEqual(ctx.user_id, "usr_a")


if __name__ == "__main__":
    unittest.main()