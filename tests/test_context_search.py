"""Phase 4 — Semantic Search + deterministic ranking tests."""

import unittest

from core.context import (
    ContextValidationError,
    LexicalSemanticSearch,
    SearchQuery,
)
from core.memory import MemoryStatusFilter

from .context_support import FakeClock, make_search, make_service, seed


class TestLexicalSearch(unittest.TestCase):
    def setUp(self):
        self.service = make_service()
        self.search = make_search(self.service)
        self.bug = seed(
            self.service,
            "user.email raises null reference when user object is missing",
            repository="digital-brain",
            file="core/auth/login.py",
        )

    def test_lexical_search_finds_relevant(self):
        results = self.search.search(
            SearchQuery(user_id="usr_a", text="null reference user missing")
        )
        self.assertEqual(
            [r.memory.memory_id for r in results], [self.bug.memory_id]
        )
        self.assertGreater(results[0].score, 0.0)
        self.assertIn("content", results[0].matched_fields)

    def test_no_match_returns_empty(self):
        results = self.search.search(
            SearchQuery(user_id="usr_a", text="zzqqw vxmmpl rocket launcher")
        )
        self.assertEqual(results, [])

    def test_query_keywords_expand_match(self):
        results = self.search.search(
            SearchQuery(user_id="usr_a", text="some unrelated riff",
                        keywords=["null", "reference"])
        )
        self.assertEqual([r.memory.memory_id for r in results], [self.bug.memory_id])

    def test_other_user_empty(self):
        results = self.search.search(
            SearchQuery(user_id="usr_nobody", text="null reference")
        )
        self.assertEqual(results, [])

    def test_cross_user_never_returned(self):
        seed(
            self.service,
            "user.balance about nothing related",
            user_id="usr_b",
            repository="digital-brain",
            file="core/auth/login.py",
        )
        results = self.search.search(
            SearchQuery(user_id="usr_a", text="null reference")
        )
        ids = {r.memory.memory_id for r in results}
        self.assertLessEqual(ids, {self.bug.memory_id})


class TestRanking(unittest.TestCase):
    def _rank(self, service, *, repository="digital-brain", file=None, text="flobnac token cache"):
        search = make_search(service)
        return search.search(
            SearchQuery(
                user_id="usr_a", text=text, repository=repository, current_file=file
            )
        )

    def test_importance_affects_ranking(self):
        service = make_service()
        low = seed(service, "flobnac token cache invalidation on edit", repository="digital-brain", importance=0.2)
        high = seed(service, "flobnac token cache invalidation on edit", repository="digital-brain", importance=0.9)
        results = self._rank(service)
        self.assertEqual(results[0].memory.memory_id, high.memory_id)
        self.assertEqual(results[1].memory.memory_id, low.memory_id)

    def test_recency_affects_ranking(self):
        clock = FakeClock()
        service = make_service(clock)
        old = seed(service, "sync the flobnac ledger on commit", repository="digital-brain", importance=0.6)
        clock.advance(days=40)
        new = seed(service, "sync the flobnac ledger on commit", repository="digital-brain", importance=0.6)
        search = make_search(service, clock)
        results = search.search(SearchQuery(user_id="usr_a", text="flobnac ledger", repository="digital-brain"))
        self.assertEqual(results[0].memory.memory_id, new.memory_id)
        self.assertEqual(results[1].memory.memory_id, old.memory_id)

    def test_repository_relevance_affects_ranking(self):
        service = make_service()
        a = seed(service, "flobnac driver telemetry packet", repository="digital-brain", importance=0.6)
        c = seed(service, "flobnac driver telemetry packet", importance=0.6)
        b = seed(service, "flobnac driver telemetry packet", repository="other-project", importance=0.6)
        results = self._rank(service)
        order = [r.memory.memory_id for r in results]
        self.assertEqual(order, [a.memory_id, c.memory_id, b.memory_id])
        self.assertEqual(results[0].repository_match, "exact")
        self.assertEqual(results[1].repository_match, "unknown")
        self.assertEqual(results[2].repository_match, "other")

    def test_current_file_relevance_affects_ranking(self):
        service = make_service()
        same = seed(service, "flobnac parser state compaction", repository="digital-brain", file="core/auth/login.py", importance=0.6)
        other = seed(service, "flobnac parser state compaction", repository="digital-brain", file="lib/core/worker.py", importance=0.6)
        results = self._rank(service, file="core/auth/login.py")
        self.assertEqual(results[0].memory.memory_id, same.memory_id)
        self.assertEqual(results[1].memory.memory_id, other.memory_id)
        self.assertEqual(results[0].file_match, "exact")
        self.assertEqual(results[1].file_match, "other")

    def test_ranking_deterministic(self):
        service = make_service()
        seed(service, "flobnac retry backoff tuning", repository="digital-brain", importance=0.4)
        seed(service, "flobnac timeout regression found", repository="digital-brain", importance=0.9)
        seed(service, "unrelated note about scheduling", importance=0.8)
        search = make_search(service)
        q = SearchQuery(user_id="usr_a", text="flobnac timeout", repository="digital-brain")
        first = [r.model_dump() for r in search.search(q)]
        second = [r.model_dump() for r in search.search(q)]
        self.assertEqual(first, second)

    def test_top_k_bounded(self):
        service = make_service()
        seed(service, "flobnac alpha", importance=0.9)
        seed(service, "flobnac beta", importance=0.8)
        seed(service, "flobnac gamma", importance=0.7)
        results = make_search(service).search(SearchQuery(user_id="usr_a", text="flobnac", top_k=2))
        self.assertEqual(len(results), 2)


class TestSearchEdgeCases(unittest.TestCase):
    def test_missing_repository_ok(self):
        service = make_service()
        seed(service, "the pizza oven is 30 minutes away")
        results = make_search(service).search(
            SearchQuery(user_id="usr_a", text="pizza oven", repository=None)
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].repository_match, "none")

    def test_missing_current_file_ok(self):
        service = make_service()
        seed(service, "flobnac buffer overflow candidate", repository="digital-brain")
        results = make_search(service).search(
            SearchQuery(user_id="usr_a", text="flobnac buffer overflow", repository="digital-brain")
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].file_match, "none")

    def test_status_filter_honoured(self):
        service = make_service()
        active = seed(service, "flobnac historical thing archived later", importance=0.9)
        service.supersede_memory("usr_a", active.memory_id)
        search = make_search(service)
        active_results = search.search(SearchQuery(user_id="usr_a", text="flobnac"))
        self.assertEqual(active_results, [])
        any_results = search.search(
            SearchQuery(user_id="usr_a", text="flobnac", status=MemoryStatusFilter.ANY)
        )
        self.assertEqual([r.memory.memory_id for r in any_results], [active.memory_id])

    def test_invalid_query_rejected(self):
        search = make_search(make_service())
        with self.assertRaises(ContextValidationError):
            search.search("not a query")  # type: ignore[arg-type]

    def test_top_k_zero_rejected(self):
        with self.assertRaises(Exception):
            SearchQuery(user_id="usr_a", text="x", top_k=0)


if __name__ == "__main__":
    unittest.main()