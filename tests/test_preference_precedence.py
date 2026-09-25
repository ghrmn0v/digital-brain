"""Explicit preferences outrank learned ones (Phase 7 rule, Phase 8 fix).

A learned hint and a user-stated preference share one conflict key, so writing
the learned value would silently supersede what the user actually asked for.
The rule under test: explicit wins, learned evidence stays visible, and a
learned preference with no explicit counterpart is still written.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)

from core import BrainApi, build_brain_service

MOMENT = datetime(2026, 9, 25, 10, tzinfo=timezone.utc)


def acceptance_feedback(index: int, user_id: str, value: str) -> Feedback:
    return Feedback(
        feedback_id=f"fb_{user_id}_{index}",
        user_id=user_id,
        source=FeedbackSource.USER,
        kind=FeedbackKind.EXPLICIT,
        target=FeedbackTarget(memory_id="mem_target"),
        created_at=MOMENT,
        label=f"prefer {value}",
        metadata={
            "signal": "accepted",
            "preference_domain": "language",
            "preference_name": "language",
            "preference_value": value,
        },
    )


class ExplicitPreferencePrecedenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)

    def preferences(self, user_id: str) -> list[tuple[str, str]]:
        return [
            (preference.name, preference.value)
            for preference in self.service.preferences(user_id)
        ]

    def test_a_learned_preference_never_overwrites_an_explicit_one(self) -> None:
        self.service.record_preference(
            "usr_a", name="language", value="Rust", domain="language"
        )
        for index in range(4):
            self.service.record_feedback(acceptance_feedback(index, "usr_a", "Python"))

        self.assertEqual(self.preferences("usr_a"), [("language", "Rust")])

    def test_the_learned_evidence_is_still_counted_and_visible(self) -> None:
        self.service.record_preference(
            "usr_a", name="language", value="Rust", domain="language"
        )
        for index in range(4):
            self.service.record_feedback(acceptance_feedback(index, "usr_a", "Python"))

        status = self.service.learning_status("usr_a")
        evidence = {entry.key: entry for entry in status.preference_evidence}
        self.assertIn("language:language", evidence)
        self.assertEqual(evidence["language:language"].positive, 4)

    def test_a_learned_preference_still_lands_without_an_explicit_one(self) -> None:
        for index in range(4):
            self.service.record_feedback(acceptance_feedback(index, "usr_b", "Python"))
        self.assertEqual(self.preferences("usr_b"), [("language", "Python")])

    def test_an_explicit_value_can_still_be_updated_deliberately(self) -> None:
        for index in range(4):
            self.service.record_feedback(acceptance_feedback(index, "usr_c", "Python"))
        self.assertEqual(self.preferences("usr_c"), [("language", "Python")])

        self.service.record_preference(
            "usr_c", name="language", value="Go", domain="language"
        )
        self.assertEqual(self.preferences("usr_c"), [("language", "Go")])

    def test_preference_provenance_is_kept_on_a_learned_record(self) -> None:
        for index in range(4):
            self.service.record_feedback(acceptance_feedback(index, "usr_d", "Rust"))
        memories = self.service._memory.list_memories(
            __import__("core.memory.filters", fromlist=["MemoryQuery"]).MemoryQuery(
                user_id="usr_d", limit=None
            )
        )
        learned = [
            memory
            for memory in memories
            if memory.metadata.get("learned") is True
        ]
        self.assertEqual(len(learned), 1)
        self.assertEqual(learned[0].source.provider, "learning")
        self.assertIn("evidence", learned[0].metadata)


class PrecedenceThroughTheApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.api = BrainApi(self.service)

    def test_api_read_keeps_showing_the_explicit_value(self) -> None:
        self.api.handle(
            {
                "id": "1",
                "method": "record_preference",
                "params": {
                    "user_id": "usr_api",
                    "name": "language",
                    "value": "Rust",
                    "domain": "language",
                },
            }
        )
        for index in range(4):
            self.api.handle(
                {
                    "id": f"f{index}",
                    "method": "record_feedback",
                    "params": {
                        "feedback": acceptance_feedback(index, "usr_api", "Python").model_dump(
                            mode="json"
                        )
                    },
                }
            )
        response = self.api.handle(
            {
                "id": "2",
                "method": "preferences",
                "params": {"user_id": "usr_api"},
            }
        )
        self.assertTrue(response.ok, response.error)
        values = {
            (item.name, item.value) for item in (response.result.preferences or [])
        }
        self.assertIn(("language", "Rust"), values)
        self.assertNotIn(("language", "Python"), values)


if __name__ == "__main__":
    unittest.main()
