"""Tests for the Brain's own retrieval and conversational surface.

``search`` and ``chat`` exist because the Brain owned retrieval all along but
published no way to reach it. These tests pin the properties that make them
trustworthy: memories come back, provenance survives, one user can never see
another's data, a chat answer is grounded or honestly empty, and a model answer
is never written to memory.
"""

from __future__ import annotations

import unittest

from core.service.api import BrainApi
from core.service.brain_service import build_brain_service

USER = "usr_search_test"
OTHER_USER = "usr_someone_else"
CORRELATION = "corr-search-test"


def calendar_event(
    event_id: str,
    summary: str,
    *,
    user_id: str = USER,
    correlation_id: str | None = CORRELATION,
    subject: dict | None = None,
) -> dict:
    event = {
        "id": event_id,
        "type": "source.calendar.event_created",
        "timestamp": "2026-09-26T09:00:00Z",
        "occurred_at": "2026-09-26T09:00:00Z",
        "user_id": user_id,
        "source": {"provider": "calendar"},
        "payload": {"summary": summary},
    }
    if correlation_id:
        event["correlation_id"] = correlation_id
    if subject:
        event["subject"] = subject
    return event


def whatsapp_event(
    event_id: str,
    text: str,
    *,
    user_id: str = USER,
    correlation_id: str | None = CORRELATION,
    subject: dict | None = None,
) -> dict:
    event = {
        "id": event_id,
        "type": "source.whatsapp.message_received",
        "timestamp": "2026-09-26T09:05:00Z",
        "occurred_at": "2026-09-26T09:05:00Z",
        "user_id": user_id,
        "source": {"provider": "whatsapp"},
        "payload": {"text": text},
    }
    if correlation_id:
        event["correlation_id"] = correlation_id
    if subject:
        event["subject"] = subject
    return event


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.api = BrainApi(self.service)

    def call(self, request_id: str, method: str, params: dict):
        return self.api.handle(
            {"id": request_id, "method": method, "version": "v1", "params": params}
        )

    def seed(self) -> None:
        self.service.ingest(calendar_event("evt-cal-1", "Hackathon planning meeting"))
        self.service.ingest(
            whatsapp_event("evt-wa-1", "Ayxan will bring the hackathon demo laptop")
        )

    # -- the capability that did not exist before ---------------------------
    def test_search_returns_the_ingested_memory(self) -> None:
        self.seed()
        response = self.call(
            "s1", "search", {"user_id": USER, "text": "hackathon", "limit": 10}
        )
        self.assertTrue(response.ok)
        result = response.result
        self.assertEqual(result.total_returned, 2)
        contents = " ".join(item.content for item in result.items)
        self.assertIn("Hackathon planning meeting", contents)

    def test_results_are_ranked_with_a_reason(self) -> None:
        self.seed()
        result = self.call(
            "s2", "search", {"user_id": USER, "text": "hackathon demo laptop"}
        ).result
        scores = [item.score for item in result.items]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for item in result.items:
            self.assertTrue(item.ranking_reason)

    def test_a_more_specific_query_ranks_the_better_match_first(self) -> None:
        self.seed()
        result = self.call(
            "s3", "search", {"user_id": USER, "text": "demo laptop"}
        ).result
        self.assertIn("demo laptop", result.items[0].content)

    def test_provenance_and_correlation_survive_retrieval(self) -> None:
        self.seed()
        result = self.call("s4", "search", {"user_id": USER, "text": "hackathon"}).result
        for item in result.items:
            self.assertIsNotNone(item.correlation_id)
            self.assertEqual(item.correlation_id, CORRELATION)
            self.assertEqual(item.source_provider, item.source_provider)
        providers = {item.source_provider for item in result.items}
        self.assertEqual(providers, {"calendar", "whatsapp"})

    def test_related_event_ids_are_returned(self) -> None:
        self.seed()
        result = self.call("s5", "search", {"user_id": USER, "text": "hackathon"}).result
        event_ids = {eid for item in result.items for eid in item.related_event_ids}
        self.assertEqual(event_ids, {"evt-cal-1", "evt-wa-1"})

    def test_empty_query_lists_by_rank(self) -> None:
        self.seed()
        result = self.call("s6", "search", {"user_id": USER}).result
        self.assertEqual(result.total_returned, 2)

    def test_limit_is_respected(self) -> None:
        self.seed()
        result = self.call("s7", "search", {"user_id": USER, "limit": 1}).result
        self.assertEqual(result.total_returned, 1)
        self.assertTrue(result.truncated)

    def test_memory_type_filter(self) -> None:
        self.seed()
        result = self.call(
            "s8", "search", {"user_id": USER, "memory_type": "event"}
        ).result
        self.assertEqual(result.total_returned, 1)
        self.assertEqual(result.items[0].type, "event")

    def test_a_query_with_no_match_returns_nothing_without_erroring(self) -> None:
        self.seed()
        result = self.call("s9", "search", {"user_id": USER, "text": "zzz"}).result
        self.assertEqual(result.total_returned, 0)
        self.assertEqual(result.items, [])

    def test_content_is_bounded_and_flagged(self) -> None:
        self.service.ingest(
            calendar_event("evt-long", "Planning " + ("detail " * 900))
        )
        item = self.call("s10", "search", {"user_id": USER, "text": "Planning"}).result.items[0]
        self.assertLessEqual(len(item.content), 1900)
        self.assertTrue(item.content_truncated)

    # -- user isolation, the mandatory property ---------------------------
    def test_search_never_leaks_another_users_memories(self) -> None:
        self.service.ingest(calendar_event("evt-mine", "Private plan", user_id=USER))
        self.service.ingest(
            calendar_event("evt-theirs", "Secret plan", user_id=OTHER_USER)
        )
        result = self.call("s11", "search", {"user_id": USER, "text": "plan"}).result
        contents = " ".join(item.content for item in result.items)
        self.assertIn("Private plan", contents)
        self.assertNotIn("Secret plan", contents)

    def test_another_user_sees_nothing_of_mine(self) -> None:
        self.service.ingest(calendar_event("evt-mine", "Private plan", user_id=USER))
        result = self.call(
            "s12", "search", {"user_id": OTHER_USER, "text": "plan"}
        ).result
        self.assertEqual(result.total_returned, 0)

    def test_user_id_is_required(self) -> None:
        response = self.call("s13", "search", {"text": "hackathon"})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code.value, "validation_error")

    def test_a_blank_user_id_is_refused_by_every_user_scoped_method(self) -> None:
        """A blank id is a *different* namespace, not an absent one.

        ``min_length=1`` accepts ``" "``, which would silently create a phantom
        user. The identifier contract refuses it, so every method inherits the
        rule rather than each one remembering to check.
        """
        cases = [
            ("search", {"user_id": " ", "text": "x"}),
            ("chat", {"user_id": " ", "message": "hi"}),
            ("preferences", {"user_id": " "}),
            ("people_summary", {"user_id": " "}),
            ("learning_status", {"user_id": " "}),
            ("people_timeline", {"user_id": " ", "person_id": "per_x"}),
            ("resolve_person", {"user_id": " ", "name": "Ayxan"}),
        ]
        for method, params in cases:
            with self.subTest(method=method):
                response = self.call(f"blank-{method}", method, params)
                self.assertFalse(response.ok, f"{method} accepted a blank user_id")
                self.assertEqual(
                    response.error.code.value,
                    "validation_error",
                    f"{method} reported the wrong code for a blank user_id",
                )

    def test_a_person_filter_cannot_reach_another_users_memory(self) -> None:
        resolution = self.service.resolve_person(USER, "Ayxan")
        self.service.ingest(
            whatsapp_event(
                "evt-wa-p",
                "Ayxan confirmed the demo",
                subject={"person_id": resolution.person_id},
            )
        )
        mine = self.call(
            "s14",
            "search",
            {"user_id": USER, "person_id": resolution.person_id},
        ).result
        # Two memories legitimately link to Ayxan here: the identity written by
        # resolve_person and the WhatsApp interaction. The point of the test is
        # the boundary, not the count.
        self.assertGreaterEqual(mine.total_returned, 1)
        self.assertTrue(
            any("demo" in item.content for item in mine.items),
            "the interaction memory should be found by its person",
        )
        theirs = self.call(
            "s15",
            "search",
            {"user_id": OTHER_USER, "person_id": resolution.person_id},
        ).result
        self.assertEqual(theirs.total_returned, 0)

    # -- contract behaviour -------------------------------------------------
    def test_search_is_advertised_by_describe(self) -> None:
        methods = self.call("s16", "describe", {}).result.methods
        self.assertIn("search", methods)
        self.assertIn("chat", methods)

    def test_an_invalid_limit_is_a_validation_error(self) -> None:
        response = self.call("s17", "search", {"user_id": USER, "limit": 0})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code.value, "validation_error")

    def test_an_unknown_field_is_refused(self) -> None:
        response = self.call("s18", "search", {"user_id": USER, "surprise": 1})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code.value, "validation_error")


class ChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.api = BrainApi(self.service)

    def call(self, request_id: str, method: str, params: dict):
        return self.api.handle(
            {"id": request_id, "method": method, "version": "v1", "params": params}
        )

    def seed(self) -> None:
        self.service.ingest(calendar_event("evt-cal-1", "Hackathon planning meeting"))
        self.service.ingest(
            whatsapp_event("evt-wa-1", "Ayxan will bring the hackathon demo laptop")
        )

    def test_chat_answers_and_cites_the_memories_it_used(self) -> None:
        self.seed()
        result = self.call(
            "c1", "chat", {"user_id": USER, "message": "what about the hackathon?"}
        ).result
        self.assertTrue(result.answer)
        self.assertTrue(result.grounded_in)
        grounded = " ".join(g.content for g in result.grounded_in)
        self.assertIn("hackathon", grounded.lower())

    def test_chat_always_reports_its_provider_and_fallback(self) -> None:
        self.seed()
        result = self.call("c1b", "chat", {"user_id": USER, "message": "hackathon"}).result
        self.assertIsInstance(result.provider, str)
        self.assertTrue(result.provider)
        self.assertIsInstance(result.fallback_used, bool)

    def test_chat_falls_back_deterministically_without_a_model(self) -> None:
        """No Gemini configured: the answer must still come, honestly labelled."""
        self.seed()
        result = self.call("c2", "chat", {"user_id": USER, "message": "hackathon"}).result
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.provider, "context-only")
        self.assertGreater(result.confidence, 0.0)

    def test_chat_with_nothing_stored_does_not_invent_an_answer(self) -> None:
        result = self.call(
            "c3", "chat", {"user_id": "usr_empty", "message": "what do I know?"}
        ).result
        self.assertEqual(result.grounded_in, [])
        self.assertEqual(result.context_fact_count, 0)

    def test_chat_is_user_isolated(self) -> None:
        self.service.ingest(calendar_event("evt-mine", "Private plan", user_id=USER))
        result = self.call(
            "c4", "chat", {"user_id": OTHER_USER, "message": "what is my plan?"}
        ).result
        self.assertEqual(result.grounded_in, [])
        self.assertNotIn("Private plan", result.answer)

    def test_chat_requires_a_user_and_a_message(self) -> None:
        self.assertFalse(self.call("c5", "chat", {"message": "hi"}).ok)
        self.assertFalse(self.call("c6", "chat", {"user_id": USER}).ok)
        self.assertFalse(self.call("c7", "chat", {"user_id": USER, "message": "  "}).ok)

    def test_an_unanchored_turn_learns_nothing(self) -> None:
        """The Brain never invents a traceability id, so it must not write."""
        self.seed()
        before = len(self.service.preferences(USER))
        result = self.call("c8", "chat", {"user_id": USER, "message": "hackathon"}).result
        self.assertEqual(result.learning_recorded, 0)
        self.assertEqual(len(self.service.preferences(USER)), before)

    def test_a_chat_answer_is_never_stored_as_a_memory(self) -> None:
        self.seed()
        memories_before = self.service.search(USER, text="hackathon", limit=50)
        self.call(
            "c9",
            "chat",
            {"user_id": USER, "message": "hackathon", "record_learning": False},
        )
        memories_after = self.service.search(USER, text="hackathon", limit=50)
        self.assertEqual(len(memories_before), len(memories_after))

    def test_correlation_id_is_echoed(self) -> None:
        self.seed()
        result = self.call(
            "c10",
            "chat",
            {"user_id": USER, "message": "hackathon", "correlation_id": CORRELATION},
        ).result
        self.assertEqual(result.correlation_id, CORRELATION)

    def test_session_id_is_echoed_for_conversation_continuity(self) -> None:
        self.seed()
        result = self.call(
            "c11",
            "chat",
            {"user_id": USER, "message": "hackathon", "session_id": "sess-1"},
        ).result
        self.assertEqual(result.session_id, "sess-1")

    def test_grounding_is_bounded_by_limit(self) -> None:
        for index in range(8):
            self.service.ingest(
                calendar_event(f"evt-many-{index}", f"Hackathon item {index}")
            )
        result = self.call(
            "c12", "chat", {"user_id": USER, "message": "hackathon", "limit": 3}
        ).result
        self.assertLessEqual(len(result.grounded_in), 3)

    def test_the_service_layer_exposes_the_same_guarantees(self) -> None:
        self.seed()
        outcome = self.service.chat(USER, "hackathon")
        self.assertTrue(outcome.answer)
        self.assertTrue(outcome.provider)
        self.assertIsInstance(outcome.fallback_used, bool)


if __name__ == "__main__":
    unittest.main()
