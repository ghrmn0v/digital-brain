"""Phase 4 — traceability tests (memory ids, scores, sources, reasons)."""

import unittest

from core.context import ContextEngine, SearchQuery

from .context_support import make_dev_context, make_search, make_service, seed


class TestTraceability(unittest.TestCase):
    def setUp(self):
        self.service = make_service()
        self.bug = seed(
            self.service,
            "potential null deref in user.email registration flow",
            repository="digital-brain",
            file="core/auth/login.py",
            kind="bug_finding",
            source_event_id="evt_abc123",
            provider="product",
            importance=0.8,
        )
        self.search = make_search(self.service)
        self.engine = ContextEngine(self.search)

    def test_memory_ids_preserved(self):
        ctx = self.engine.build_context(make_dev_context(task="null deref"))
        ids = {r.memory.memory_id for r in ctx.relevant_memories}
        self.assertIn(self.bug.memory_id, ids)
        self.assertEqual(ctx.previous_bug_findings, [self.bug.memory_id])

    def test_scores_and_order_preserved(self):
        high = seed(self.service, "null deref in checkout totals", repository="digital-brain", importance=0.9)
        results = self.search.search(
            SearchQuery(user_id="usr_a", text="null deref", repository="digital-brain")
        )
        scores = [r.score for r in results]
        self.assertTrue(all(0.0 <= score <= 1.0 for score in scores))
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(
            [r.memory.memory_id for r in results],
            [high.memory_id, self.bug.memory_id],
        )

    def test_source_and_event_traceability(self):
        ctx = self.engine.build_context(make_dev_context(task="null deref"))
        (scored,) = ctx.relevant_memories
        self.assertEqual(scored.memory.source.provider, "product")
        self.assertEqual(scored.memory.metadata["source_event_id"], "evt_abc123")
        self.assertEqual(scored.memory.memory_id, self.bug.memory_id)

    def test_ranking_reason_and_matched_fields(self):
        ctx = self.engine.build_context(make_dev_context(task="null deref"))
        (scored,) = ctx.relevant_memories
        self.assertTrue(scored.ranking_reason)
        self.assertIn("lex=", scored.ranking_reason)
        self.assertIn("repo=", scored.ranking_reason)
        self.assertIn("file=", scored.ranking_reason)
        self.assertIn("content", scored.matched_fields)
        self.assertIn("repository", scored.matched_fields)
        self.assertIn("category", scored.matched_fields)

    def test_search_metadata_present(self):
        ctx = self.engine.build_context(make_dev_context(task="null deref"))
        self.assertEqual(ctx.search_metadata.queries, ["null deref"])
        self.assertEqual(ctx.search_metadata.candidates_considered, 1)
        self.assertTrue(ctx.search_metadata.repository_aware)
        self.assertTrue(ctx.search_metadata.file_aware)
        self.assertEqual(ctx.search_metadata.status, "ok")


if __name__ == "__main__":
    unittest.main()