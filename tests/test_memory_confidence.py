"""Confidence handling — preservation and provenance baselines."""

import unittest

from core.memory import MemoryCandidate, MemoryValidationError
from core.memory.confidence import (
    CONFLICTING_CONFIDENCE,
    DEFAULT_CONFIDENCE,
    EXPLICIT_CONFIDENCE,
    EXTERNAL_CONFIDENCE,
    INFERRED_CONFIDENCE,
    resolve_confidence,
)

from .memory_support import linkedin_source


def resolve(**candidate_kwargs) -> float:
    data = dict(content="x", user_id="usr_1")
    data.update(candidate_kwargs)
    return resolve_confidence(MemoryCandidate(**data))


class TestConfidence(unittest.TestCase):
    def test_provided_confidence_preserved(self):
        self.assertEqual(resolve(confidence=0.83), 0.83)

    def test_no_source_defaults(self):
        self.assertEqual(resolve(), DEFAULT_CONFIDENCE)

    def test_user_provider_is_explicit(self):
        from contracts.common.types import Source

        self.assertEqual(
            resolve(source=Source(provider="user")), EXPLICIT_CONFIDENCE
        )

    def test_explicit_flag(self):
        self.assertEqual(resolve(metadata={"explicit": True}), EXPLICIT_CONFIDENCE)

    def test_structured_external_providers(self):
        for provider in ("linkedin", "whatsapp", "calendar", "tasks", "jobs"):
            from contracts.common.types import Source

            self.assertEqual(
                resolve(source=Source(provider=provider)), EXTERNAL_CONFIDENCE
            )

    def test_inferred_low(self):
        self.assertEqual(resolve(metadata={"inferred": True}), INFERRED_CONFIDENCE)

    def test_conflicting_evidence(self):
        self.assertEqual(
            resolve(metadata={"conflicting_evidence": True}),
            CONFLICTING_CONFIDENCE,
        )

    def test_unknown_provider_falls_back(self):
        from contracts.common.types import Source

        self.assertEqual(
            resolve(source=Source(provider="mystery")), DEFAULT_CONFIDENCE
        )

    def test_out_of_range_rejected(self):
        with self.assertRaises(MemoryValidationError):
            resolve(confidence=1.5)


if __name__ == "__main__":
    unittest.main()