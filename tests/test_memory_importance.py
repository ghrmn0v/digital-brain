"""Importance baseline — deterministic rule table."""

import unittest

from contracts.memory.memory import MemoryType
from core.memory import MemoryCandidate, MemoryValidationError
from core.memory.importance import BASE_IMPORTANCE, baseline_importance

from .memory_support import linkedin_source


def score(**candidate_kwargs) -> float:
    data = dict(content="x", user_id="usr_1", source=linkedin_source())
    data.update(candidate_kwargs)
    return baseline_importance(MemoryCandidate(**data), confidence=0.7)


class TestImportance(unittest.TestCase):
    def test_base(self):
        self.assertEqual(score(), BASE_IMPORTANCE)

    def test_preference_bonus(self):
        self.assertEqual(
            score(type=MemoryType.PREFERENCE), BASE_IMPORTANCE + 0.25
        )

    def test_relationship_bonus(self):
        self.assertEqual(
            score(type=MemoryType.RELATIONSHIP), BASE_IMPORTANCE + 0.20
        )

    def test_interaction_penalty_and_people_bonus(self):
        self.assertEqual(score(type=MemoryType.INTERACTION), BASE_IMPORTANCE - 0.10)
        self.assertEqual(
            score(related_people=["per_1"]), BASE_IMPORTANCE + 0.10
        )

    def test_explicit_bonus(self):
        self.assertEqual(
            score(metadata={"explicit": True}), BASE_IMPORTANCE + 0.15
        )

    def test_major_event_bonus(self):
        self.assertEqual(
            score(metadata={"major_event": True}), BASE_IMPORTANCE + 0.20
        )

    def test_temporary_penalty(self):
        self.assertEqual(
            score(metadata={"temporary": True}), BASE_IMPORTANCE - 0.30
        )

    def test_high_confidence_bonus(self):
        self.assertEqual(
            baseline_importance(
                MemoryCandidate(content="x", user_id="usr_1", source=linkedin_source()),
                confidence=0.95,
            ),
            BASE_IMPORTANCE + 0.05,
        )

    def test_clamped_to_one(self):
        self.assertEqual(
            score(
                type=MemoryType.PREFERENCE,
                related_people=["per_1"],
                metadata={"explicit": True, "major_event": True},
            ),
            1.0,
        )

    def test_not_below_zero(self):
        self.assertEqual(
            score(type=MemoryType.INTERACTION, metadata={"temporary": True}),
            max(0.0, BASE_IMPORTANCE - 0.10 - 0.30),
        )
        self.assertGreaterEqual(score(metadata={"temporary": True}), 0.0)

    def test_explicit_importance_wins(self):
        self.assertEqual(
            score(importance=0.99, type=MemoryType.PREFERENCE), 0.99
        )

    def test_out_of_range_importance_rejected(self):
        with self.assertRaises(MemoryValidationError):
            score(importance=1.5)


if __name__ == "__main__":
    unittest.main()