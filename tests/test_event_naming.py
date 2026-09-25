"""Event naming must not decide whether the Brain learns anything.

A connector names the same real-world thing differently from the Brain: a job
posting is ``job_seen`` to Core and ``job.discovered`` to whoever wrote the
producer. Both are schema-valid. Before action synonyms were resolved, the
second one was receipted and produced no memory, which a caller could not
distinguish from having learned something — silent data loss on a real event
type.

These tests pin both halves: known synonyms reach memory, and an event with no
rule at all is reported rather than hidden.
"""

from __future__ import annotations

import unittest

from contracts.events.source_event import NormalizedSourceEvent
from core.ingestion.handlers import find_rule, rule_key
from core.service.brain_service import build_brain_service


def event(event_type: str, provider: str = "linkedin", **payload) -> dict:
    return {
        "id": f"evt-{abs(hash(event_type)) % 10_000}",
        "type": event_type,
        "timestamp": "2026-09-26T09:00:00Z",
        "occurred_at": "2026-09-26T09:00:00Z",
        "user_id": "usr_naming",
        "source": {"provider": provider},
        "payload": payload,
        "correlation_id": "corr-naming",
    }


def parsed(event_type: str, provider: str = "linkedin", **payload) -> NormalizedSourceEvent:
    return NormalizedSourceEvent.model_validate(event(event_type, provider, **payload))


class ActionSynonymTests(unittest.TestCase):
    def test_the_canonical_name_resolves(self) -> None:
        self.assertEqual(
            rule_key(parsed("source.linkedin.job_seen", company="Acme")),
            ("linkedin", "job_seen"),
        )

    def test_the_producer_spelling_resolves_to_the_same_rule(self) -> None:
        """This is the real defect: Product emits job_discovered."""
        for alias in ("job_discovered", "job_found", "job_viewed"):
            with self.subTest(alias=alias):
                self.assertEqual(
                    rule_key(parsed(f"source.linkedin.{alias}", company="Acme")),
                    ("linkedin", "job_seen"),
                    f"{alias} did not resolve to the job_seen rule",
                )

    def test_profile_synonyms_resolve(self) -> None:
        self.assertEqual(
            rule_key(parsed("source.linkedin.profile_viewed", full_name="Ayxan")),
            ("linkedin", "profile_updated"),
        )

    def test_an_exact_match_still_wins_over_a_synonym(self) -> None:
        self.assertEqual(
            rule_key(parsed("source.linkedin.job_seen", company="Acme")),
            ("linkedin", "job_seen"),
        )

    def test_a_genuinely_unknown_action_resolves_to_nothing(self) -> None:
        self.assertIsNone(rule_key(parsed("source.linkedin.totally_made_up")))
        self.assertIsNone(find_rule(parsed("source.linkedin.totally_made_up")))

    def test_the_contract_rejects_a_type_outside_the_source_namespace(self) -> None:
        """The pattern is the first line of defence; find_rule's guard is second."""
        import pydantic

        for event_type in ("job.discovered", "not-a-source-type", "source.linkedin"):
            with self.subTest(event_type=event_type):
                with self.assertRaises(pydantic.ValidationError):
                    parsed(event_type, company="Acme")

    def test_find_rule_guards_a_non_source_type_defensively(self) -> None:
        """Unreachable through the typed model, so exercised directly."""

        class Untyped:
            type = "job.discovered"

        self.assertIsNone(find_rule(Untyped()))  # type: ignore[arg-type]

    def test_a_synonym_enforces_the_canonical_required_fields(self) -> None:
        """job_seen requires `company`; the synonym must require it too."""
        service = build_brain_service(":memory:")
        result = service.ingest(event("source.linkedin.job_discovered", title="Engineer"))
        self.assertEqual(result.outcome.value, "rejected")
        self.assertIn("company", result.reason or "")


class MemoryIsActuallyCreatedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")

    def test_a_synonym_produces_the_same_memory_as_the_canonical_name(self) -> None:
        canonical = self.service.ingest(
            event("source.linkedin.job_seen", company="Acme", title="Engineer")
        )
        synonym = self.service.ingest(
            event(
                "source.linkedin.job_discovered",
                company="Acme",
                title="Engineer",
            )
        )
        self.assertEqual(canonical.outcome.value, "accepted")
        self.assertEqual(synonym.outcome.value, "accepted")
        self.assertEqual(len(synonym.memory_ids), 1, "the synonym learned nothing")
        memory = self.service._get_memory_safe("usr_naming", synonym.memory_ids[0])
        self.assertEqual(memory.content, canonical and memory.content)
        self.assertIn("Acme", memory.content)
        self.assertIn("Engineer", memory.content)

    def test_an_unmapped_event_is_reported_not_hidden(self) -> None:
        """Still valid and receipted, but the caller is told nothing was learned."""
        result = self.service.ingest(event("source.linkedin.totally_made_up", x=1))
        self.assertEqual(result.outcome.value, "accepted")
        self.assertEqual(result.memory_ids, ())
        self.assertIsNotNone(result.reason)
        self.assertIn("no mapping rule", result.reason)
        self.assertIn("totally_made_up", result.reason)

    def test_a_mapped_event_carries_no_spurious_reason(self) -> None:
        result = self.service.ingest(
            event("source.linkedin.job_discovered", company="Acme")
        )
        self.assertIsNone(result.reason)

    def test_an_unmapped_event_is_still_receipted_for_dedup(self) -> None:
        first = self.service.ingest(event("source.linkedin.totally_made_up", x=1))
        second = self.service.ingest(event("source.linkedin.totally_made_up", x=1))
        self.assertEqual(first.outcome.value, "accepted")
        self.assertEqual(second.outcome.value, "duplicate")


class ProcessorSharesOneResolutionTests(unittest.TestCase):
    """Validation and processing must never disagree about a rule."""

    def test_the_processor_resolves_synonyms_too(self) -> None:
        service = build_brain_service(":memory:")
        result = service.ingest(
            event("source.linkedin.job_found", company="Acme", title="Engineer")
        )
        self.assertEqual(len(result.memory_ids), 1)

    def test_provenance_records_the_type_that_actually_arrived(self) -> None:
        """The alias resolved, but the record must not misreport the sender.

        Storing the canonical name would claim Core received `job_seen` when it
        received `job_discovered`, which is exactly the kind of quiet
        rewrite-of-history that makes provenance worthless.
        """
        service = build_brain_service(":memory:")
        result = service.ingest(
            event("source.linkedin.job_discovered", company="Acme", title="Engineer")
        )
        memory = service._get_memory_safe("usr_naming", result.memory_ids[0])
        self.assertEqual(
            memory.metadata.get("event_type"), "source.linkedin.job_discovered"
        )
        self.assertEqual(list(memory.related_events), [result.event_id])


if __name__ == "__main__":
    unittest.main()
