"""Phase 4 — isolation / security tests (the critical boundary)."""

import unittest

from core.context import ContextEngine, SearchQuery

from .context_support import make_dev_context, make_search, make_service, seed


class TestIsolation(unittest.TestCase):
    def setUp(self):
        self.service = make_service()
        self.search = make_search(self.service)
        self.a = seed(
            self.service,
            "null reference in user.email found during login",
            user_id="usr_a",
            repository="digital-brain",
            file="core/auth/login.py",
            kind="bug_finding",
        )
        self.b = seed(
            self.service,
            "null reference in user.email found during login",
            user_id="usr_b",
            repository="digital-brain",
            file="core/auth/login.py",
            kind="bug_finding",
        )
        self.engine = ContextEngine(self.search)

    def test_user_a_cannot_retrieve_user_b_memory(self):
        results = self.search.search(
            SearchQuery(user_id="usr_a", text="null reference login")
        )
        ids = {r.memory.memory_id for r in results}
        self.assertIn(self.a.memory_id, ids)
        self.assertNotIn(self.b.memory_id, ids)

    def test_user_b_cannot_retrieve_user_a_memory(self):
        results = self.search.search(
            SearchQuery(user_id="usr_b", text="null reference login")
        )
        ids = {r.memory.memory_id for r in results}
        self.assertIn(self.b.memory_id, ids)
        self.assertNotIn(self.a.memory_id, ids)

    def test_repository_match_cannot_bypass_isolation(self):
        # Memory B lives in the same repository AND same file as user A's query.
        results = self.search.search(
            SearchQuery(
                user_id="usr_a",
                text="null reference in user.email found during login",
                repository="digital-brain",
                current_file="core/auth/login.py",
            )
        )
        ids = {r.memory.memory_id for r in results}
        self.assertNotIn(self.b.memory_id, ids)

    def test_engine_respects_user_scoping(self):
        ctx = self.engine.build_context(
            make_dev_context(task="null reference in user.email")
        )
        ids = {r.memory.memory_id for r in ctx.relevant_memories}
        self.assertIn(self.a.memory_id, ids)
        self.assertNotIn(self.b.memory_id, ids)

    def test_spoofed_user_id_in_user_context_ignored(self):
        dev = make_dev_context(
            task="null reference in user.email",
            user_context={
                "user_id": "usr_b",
                "current_user": "usr_b",
                "task": "null reference in user.email",
            },
        )
        ctx = self.engine.build_context(dev)
        self.assertEqual(ctx.user_id, "usr_a")
        ids = {r.memory.memory_id for r in ctx.relevant_memories}
        self.assertNotIn(self.b.memory_id, ids)

    def test_repository_a_does_not_dominate_repository_b(self):
        # A's own context never surfaces B's repository-only memories.
        b_other = seed(
            self.service,
            "secret api keys rotation checklist",
            user_id="usr_b",
            repository="secret-repo",
        )
        results = self.search.search(
            SearchQuery(
                user_id="usr_a",
                text="null reference login",
                repository="digital-brain",
            )
        )
        ids = {r.memory.memory_id for r in results}
        self.assertNotIn(b_other.memory_id, ids)


if __name__ == "__main__":
    unittest.main()