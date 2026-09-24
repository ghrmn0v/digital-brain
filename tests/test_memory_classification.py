"""Classification — deterministic rules (no LLM)."""

import unittest

from contracts.memory.memory import MemoryType
from core.memory import MemoryClassifier, MemoryCandidate

from .memory_support import linkedin_source


def classify(**candidate_kwargs) -> MemoryType:
    data = dict(content="some text", user_id="usr_1", source=linkedin_source())
    data.update(candidate_kwargs)
    return MemoryClassifier().classify(MemoryCandidate(**data))


class TestClassification(unittest.TestCase):
    def test_default_is_fact(self):
        self.assertEqual(classify(), MemoryType.FACT)

    def test_explicit_type_is_preserved(self):
        self.assertEqual(
            classify(type=MemoryType.RELATIONSHIP), MemoryType.RELATIONSHIP
        )

    def test_kind_preference(self):
        self.assertEqual(
            classify(metadata={"kind": "preference"}), MemoryType.PREFERENCE
        )

    def test_kind_relationship(self):
        self.assertEqual(
            classify(metadata={"kind": "relationship"}), MemoryType.RELATIONSHIP
        )

    def test_kind_interaction_and_conversation(self):
        self.assertEqual(
            classify(metadata={"kind": "interaction"}), MemoryType.INTERACTION
        )
        self.assertEqual(
            classify(metadata={"kind": "conversation"}), MemoryType.INTERACTION
        )

    def test_kind_task_context_maps_to_episode(self):
        for kind in ("task", "task_context"):
            self.assertEqual(
                classify(metadata={"kind": kind}), MemoryType.EPISODE
            )

    def test_kind_event(self):
        self.assertEqual(classify(metadata={"kind": "event"}), MemoryType.EVENT)

    def test_kind_fact(self):
        self.assertEqual(classify(metadata={"kind": "fact"}), MemoryType.FACT)

    def test_unknown_kind_maps_to_observation(self):
        self.assertEqual(
            classify(metadata={"kind": "weird"}), MemoryType.OBSERVATION
        )

    def test_temporary_maps_to_episode(self):
        self.assertEqual(
            classify(metadata={"temporary": True}), MemoryType.EPISODE
        )

    def test_explicit_type_beats_metadata_kind(self):
        self.assertEqual(
            classify(type=MemoryType.EVENT, metadata={"kind": "preference"}),
            MemoryType.EVENT,
        )


if __name__ == "__main__":
    unittest.main()