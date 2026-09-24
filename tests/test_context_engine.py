"""Phase 4 — ContextEngine assembly and failure behavior."""

import unittest

from core import build_gateway
from core.context import (
    ContextEngine,
    ContextLimits,
    ContextStatus,
    ContextValidationError,
    SearchQuery,
)
from core.memory import MemoryQuery
from core.understanding import DeveloperContext
from core.understanding.exceptions import UnderstandingError

from .context_support import (
    FailingSearch,
    FakeClock,
    make_dev_context,
    make_search,
    make_service,
    seed,
)


class FailingUnderstanding:
    def understand(self, corpus, *, user_id=None, corpus_id=None):
        raise UnderstandingError("simulated understanding failure")


def make_engine(search, **kwargs):
    return ContextEngine(search, **kwargs)


class TestContextEngine(unittest.TestCase):
    def setUp(self):
        self.service = make_service()
        self.search = make_search(self.service)
        self.engine = make_engine(self.search)

    def test_builds_context_preserving_developer_context(self):
        seeded = seed(
            self.service,
            "login null reference when user missing",
            repository="digital-brain",
            file="core/auth/login.py",
            kind="bug_finding",
        )
        dev = make_dev_context(repository="digital-brain", current_file="core/auth/login.py", task="Investigate null reference")
        ctx = self.engine.build_context(dev)
        self.assertEqual(ctx.status, ContextStatus.FULL)
        self.assertEqual(ctx.user_id, "usr_a")
        self.assertEqual(ctx.repository, "digital-brain")
        self.assertEqual(ctx.current_file, "core/auth/login.py")
        self.assertEqual(ctx.current_line, 42)
        self.assertEqual(ctx.current_task, "Investigate null reference")
        self.assertIs(ctx.developer_context, dev)
        self.assertEqual([r.memory.memory_id for r in ctx.relevant_memories], [seeded.memory_id])
        self.assertEqual(ctx.previous_bug_findings, [seeded.memory_id])

    def test_understanding_integration_phase3(self):
        seed(self.service, "null reference bug in user.email", kind="bug_finding", repository="digital-brain", file="core/auth/login.py")
        gateway = build_gateway()
        engine = make_engine(self.search, understanding=gateway)
        ctx = engine.build_context(make_dev_context(task="fix the null reference in user.email"))
        self.assertIsNotNone(ctx.understanding)
        self.assertEqual(ctx.understanding.user_id, "usr_a")
        self.assertEqual(ctx.understanding.provider, "heuristic")
        self.assertGreater(len(ctx.search_metadata.keywords), 0)
        # deterministic across two independent builds
        again = engine.build_context(make_dev_context(task="fix the null reference in user.email"))
        self.assertEqual(
            [r.memory.memory_id for r in ctx.relevant_memories],
            [r.memory.memory_id for r in again.relevant_memories],
        )

    def test_understanding_failure_degrades_nothing(self):
        seed(self.service, "flobnac thing", repository="digital-brain")
        engine = make_engine(self.search, understanding=FailingUnderstanding())
        ctx = engine.build_context(make_dev_context(task="flobnac thing"))
        self.assertIsNone(ctx.understanding)
        self.assertNotEqual(ctx.status, ContextStatus.DEGRADED)
        self.assertEqual(len(ctx.relevant_memories), 1)

    def test_top_k_limit_enforced(self):
        for i in range(5):
            seed(self.service, f"flobnac module {i} cache invalidation", repository="digital-brain", importance=0.5 + i * 0.05)
        engine = make_engine(
            self.search,
            limits=ContextLimits(top_memories=3, top_bug_findings=0, top_decisions=0, top_preferences=0, max_total_memories=3),
        )
        ctx = engine.build_context(make_dev_context(task="flobnac cache"))
        self.assertEqual(len(ctx.relevant_memories), 3)
        expected = [
            r.memory.memory_id
            for r in self.search.search(
                SearchQuery(
                    user_id="usr_a",
                    text="flobnac cache",
                    repository="digital-brain",
                    top_k=3,
                )
            )
        ]
        self.assertEqual([r.memory.memory_id for r in ctx.relevant_memories], expected)

    def test_category_quotas_included(self):
        seed(self.service, "general flobnac topic one", repository="digital-brain", importance=0.9)
        seed(self.service, "general flobnac topic two", repository="digital-brain", importance=0.8)
        bug = seed(self.service, "a completely unrelated historical note", repository="digital-brain", file="core/auth/login.py", kind="bug_finding")
        dec = seed(self.service, "another unrelated note", repository="digital-brain", kind="decision")
        pref = seed(self.service, "prefers terse summaries", kind="preference", repository="digital-brain")
        engine = make_engine(
            self.search,
            limits=ContextLimits(top_memories=2, top_bug_findings=1, top_decisions=1, top_preferences=1, max_total_memories=5),
        )
        ctx = engine.build_context(make_dev_context(task="flobnac topic details"))
        ids = {r.memory.memory_id for r in ctx.relevant_memories}
        self.assertIn(bug.memory_id, ids)
        self.assertIn(dec.memory_id, ids)
        self.assertIn(pref.memory_id, ids)
        self.assertEqual(ctx.previous_bug_findings, [bug.memory_id])
        self.assertEqual(ctx.previous_decisions, [dec.memory_id])
        self.assertEqual(ctx.developer_preferences, [pref.memory_id])
        self.assertLessEqual(len(ctx.relevant_memories), 5)

    def test_empty_memory_result_current_only(self):
        seed(self.service, "completely unrelated parking garage notes")
        ctx = self.engine.build_context(make_dev_context(task="flobnac quadrupole beamline"))
        self.assertEqual(ctx.status, ContextStatus.CURRENT_ONLY)
        self.assertEqual(ctx.relevant_memories, [])
        self.assertEqual(ctx.search_metadata.status, "ok")
        self.assertEqual(ctx.user_id, "usr_a")

    def test_memoryless_user_current_only(self):
        ctx = self.engine.build_context(make_dev_context())
        self.assertEqual(ctx.status, ContextStatus.CURRENT_ONLY)
        self.assertIsNone(ctx.understanding)

    def test_missing_current_file_handled(self):
        seed(self.service, "flobnac repository rule updated", repository="digital-brain")
        ctx = self.engine.build_context(make_dev_context(current_file=None, task="flobnac"))
        self.assertFalse(ctx.search_metadata.file_aware)
        self.assertEqual(ctx.status, ContextStatus.FULL)
        self.assertIsNone(ctx.current_file)

    def test_missing_repository_metadata_handled(self):
        seeded = seed(self.service, "flobnac retry backoff configured for the gateway")
        ctx = self.engine.build_context(make_dev_context(task="flobnac retry backoff"))
        self.assertEqual(ctx.status, ContextStatus.FULL)
        self.assertTrue(ctx.search_metadata.repository_aware)
        self.assertEqual([r.memory.memory_id for r in ctx.relevant_memories], [seeded.memory_id])

    def test_current_task_from_user_context(self):
        seed(self.service, "flobnac deploy window tuesday", repository="digital-brain")
        dev = make_dev_context(user_context={"task_description": "flobnac deploy"})
        ctx = self.engine.build_context(dev)
        self.assertEqual(ctx.current_task, "flobnac deploy")

    def test_input_not_developer_context_raises(self):
        with self.assertRaises(ContextValidationError):
            self.engine.build_context("not a context")  # type: ignore[arg-type]

    def test_invalid_limits_raise(self):
        with self.assertRaises(ContextValidationError):
            make_engine(self.search, limits=ContextLimits(top_memories=10, max_total_memories=1))

    def test_bad_search_port_raises(self):
        with self.assertRaises(TypeError):
            ContextEngine("not a searcher")  # type: ignore[arg-type]


class TestFailureBehavior(unittest.TestCase):
    def test_search_failure_produces_structured_degraded(self):
        engine = make_engine(FailingSearch(), now=FakeClock().now)
        ctx = engine.build_context(make_dev_context(repository="digital-brain", current_file="core/auth/login.py", task="null ref"))
        self.assertEqual(ctx.status, ContextStatus.DEGRADED)
        self.assertEqual(ctx.relevant_memories, [])
        self.assertEqual(ctx.previous_bug_findings, [])
        self.assertEqual(ctx.search_metadata.status, "degraded")
        self.assertIn("store outage", ctx.search_metadata.error or "")
        self.assertEqual(ctx.user_id, "usr_a")
        self.assertEqual(ctx.repository, "digital-brain")
        self.assertEqual(ctx.current_file, "core/auth/login.py")
        self.assertEqual(ctx.current_task, "null ref")


if __name__ == "__main__":
    unittest.main()