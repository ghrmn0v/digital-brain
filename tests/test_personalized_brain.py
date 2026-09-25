"""Brain context assembly, learning routing and personalized reasoning.

These tests cover the rule that makes the Brain more than a prompt wrapper:

* only relevant, user-scoped context reaches a provider;
* a provider's answer is validated, never trusted;
* a provider's suggestion becomes a **candidate**, and only evidence-backed
  candidates reach the existing Learning Engine;
* an explicit user preference still outranks a learned one.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from contracts.common.types import Source
from contracts.memory.memory import MemoryType

from core.context.personalization import (
    PersonalContextBuilder,
    personal_system_prompt,
    personalized_user_prompt,
    render_personal_context,
)
from core.context.search import LexicalSemanticSearch
from core.learning.candidates import (
    LearningCandidate,
    LearningCandidateKind,
    LearningEvidence,
    PersonalizedAnswer,
    candidate_to_feedback,
    route_candidates,
)
from core.memory import MemoryCandidate
from core.people import PeopleIntelligence
from core.service.brain_service import build_brain_service
from core.understanding import HeuristicProvider, LLMGateway, LLMProvider, LLMRequest
from core.understanding.exceptions import LLMProviderError

NOW = datetime(2026, 9, 25, 10, tzinfo=timezone.utc)


def seed_memory(service, *, user_id, content, metadata=None, memory_type=MemoryType.FACT):
    return service._memory.create_memory(
        MemoryCandidate(
            content=content,
            user_id=user_id,
            type=memory_type,
            source=Source(provider="whatsapp"),
            metadata=metadata or {},
        )
    )


class ScriptedProvider(LLMProvider):
    """Returns canned provider text so structured output can be exercised."""

    name = "scripted"

    def __init__(self, text: str) -> None:
        self._text = text
        self.seen: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> str:
        self.seen.append(request)
        return self._text


class ContextAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.builder = PersonalContextBuilder(
            LexicalSemanticSearch(self.service._memory),
            people=self.service._people,
            learning=self.service._learning,
        )

    def test_relevant_memory_is_included(self) -> None:
        seed_memory(
            self.service,
            user_id="usr_a",
            content="The user prefers TypeScript for backend services",
        )
        seed_memory(
            self.service,
            user_id="usr_a",
            content="The user owns a bicycle",
        )
        context = self.builder.build("usr_a", "Which backend language should I use?")
        texts = " ".join(fact.text for fact in context.memories)
        self.assertIn("TypeScript", texts)
        self.assertNotIn("bicycle", texts, "unrelated memory must not be included")

    def test_context_is_bounded(self) -> None:
        for index in range(20):
            seed_memory(
                self.service,
                user_id="usr_a",
                content=f"backend deployment note {index} about kubernetes",
            )
        context = self.builder.build("usr_a", "kubernetes deployment")
        self.assertLessEqual(len(context.memories), 8)
        for fact in context.memories:
            self.assertLessEqual(len(fact.text), 300)

    def test_context_is_user_scoped(self) -> None:
        seed_memory(self.service, user_id="usr_a", content="the language I like is Rust")
        seed_memory(self.service, user_id="usr_b", content="the language I like is Go")
        mine = self.builder.build("usr_a", "which language do I like, Rust or Go?")
        theirs = self.builder.build("usr_b", "which language do I like, Rust or Go?")
        mine_text = " ".join(fact.text for fact in mine.memories)
        theirs_text = " ".join(fact.text for fact in theirs.memories)
        self.assertIn("Rust", mine_text)
        self.assertNotIn("Go", mine_text)
        self.assertIn("Go", theirs_text)
        self.assertNotIn("Rust", theirs_text)

    def test_explicit_and_learned_preferences_are_labelled(self) -> None:
        self.service.record_preference(
            "usr_a", name="backend_language", value="TypeScript", domain="language"
        )
        context = self.builder.build("usr_a", "what backend language?")
        sources = {fact.source for fact in context.preferences}
        self.assertIn("explicit", sources)
        self.assertNotIn("learned", sources)

    def test_people_are_only_included_when_mentioned(self) -> None:
        resolution = self.service._people.resolve_person("usr_a", "Ali Ahmadov")
        seed_memory(
            self.service,
            user_id="usr_a",
            content="Ali Ahmadov works at Acme",
        )
        mentioned = self.builder.build("usr_a", "what does Ali Ahmadov do?")
        self.assertEqual(
            [fact.person_id for fact in mentioned.people], [resolution.person_id]
        )
        unrelated = self.builder.build("usr_a", "what is the weather?")
        self.assertEqual(unrelated.people, [])

    def test_learned_evidence_is_labelled_as_weak(self) -> None:
        for index in range(3):
            self.service.record_feedback(
                __import__("contracts.feedback.feedback", fromlist=["Feedback"]).Feedback(
                    feedback_id=f"fb_{index}",
                    user_id="usr_a",
                    source="user",
                    kind="explicit",
                    target={"memory_id": "mem_x"},
                    created_at=NOW,
                    label="use pytest",
                    metadata={
                        "signal": "accepted",
                        "preference_domain": "testing",
                        "preference_name": "test_runner",
                        "preference_value": "pytest",
                    },
                )
            )
        context = self.builder.build("usr_a", "how should I run tests?")
        self.assertTrue(context.learned)
        self.assertEqual({fact.source for fact in context.learned}, {"learned"})

    def test_empty_context_renders_without_fake_sections(self) -> None:
        context = self.builder.build("usr_a", "anything?")
        self.assertTrue(context.is_empty)
        self.assertEqual(render_personal_context(context), "")
        prompt = personalized_user_prompt(context)
        self.assertIn("none stored yet", prompt)

    def test_prompt_separates_context_from_the_request(self) -> None:
        self.service.record_preference(
            "usr_a", name="backend_language", value="TypeScript", domain="language"
        )
        context = self.builder.build("usr_a", "which language?")
        system = personal_system_prompt()
        prompt = personalized_user_prompt(context, instruction="answer briefly")
        self.assertIn("do not own persistent memory", system.lower())
        self.assertIn("PREFERENCES", prompt)
        self.assertIn("CURRENT REQUEST", prompt)
        self.assertIn("which language?", prompt)
        self.assertIn("TASK", prompt)
        self.assertNotIn("GEMINI", system.upper().replace("GEMINI", ""))

    def test_empty_request_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.builder.build("usr_a", "   ")


class CandidateRoutingTests(unittest.TestCase):
    def test_inference_is_not_recorded(self) -> None:
        calls: list[object] = []
        candidate = LearningCandidate(
            key="backend_language", value="Python", evidence=LearningEvidence.INFERENCE
        )
        results = route_candidates(
            [candidate], user_id="usr_a", target_event_id="evt_1", record=calls.append
        )
        self.assertEqual(calls, [], "a model guess must never reach learning")
        self.assertFalse(results[0].recorded)
        self.assertIn("not evidence-backed", results[0].reason)

    def test_explicit_candidate_becomes_explicit_feedback(self) -> None:
        calls: list[object] = []
        candidate = LearningCandidate(
            key="backend_language",
            value="TypeScript",
            evidence=LearningEvidence.EXPLICIT_STATEMENT,
            confidence=0.95,
        )
        results = route_candidates(
            [candidate], user_id="usr_a", target_event_id="evt_1", record=calls.append
        )
        self.assertEqual(len(calls), 1)
        feedback = calls[0]
        self.assertEqual(feedback.kind.value, "explicit")
        self.assertEqual(feedback.target.event_id, "evt_1")
        self.assertEqual(feedback.metadata["signal"], "accepted")
        self.assertTrue(feedback.metadata["llm_candidate"])
        self.assertTrue(results[0].recorded)

    def test_implicit_candidate_becomes_a_weak_counted_signal(self) -> None:
        calls: list[object] = []
        candidate = LearningCandidate(
            kind=LearningCandidateKind.AVOID_TOPIC,
            key="python",
            value="avoid python",
            topic="python",
            evidence=LearningEvidence.REPEATED_REJECTION,
        )
        route_candidates(
            [candidate], user_id="usr_a", target_event_id="evt_1", record=calls.append
        )
        feedback = calls[0]
        self.assertEqual(feedback.kind.value, "implicit")
        self.assertEqual(feedback.metadata["signal"], "rejected")
        self.assertEqual(feedback.label, "avoid:python")

    def test_learning_failure_does_not_break_the_brain(self) -> None:
        def exploding(_feedback):
            raise RuntimeError("state store unavailable")

        candidate = LearningCandidate(
            key="k", value="v", evidence=LearningEvidence.EXPLICIT_STATEMENT
        )
        results = route_candidates(
            [candidate], user_id="usr_a", target_event_id="evt_1", record=exploding
        )
        self.assertFalse(results[0].recorded)
        self.assertIn("learning rejected", results[0].reason)

    def test_candidate_without_evidence_target_is_rejected(self) -> None:
        candidate = LearningCandidate(
            key="k", value="v", evidence=LearningEvidence.INFERENCE
        )
        with self.assertRaises(ValueError):
            candidate_to_feedback(candidate, user_id="usr_a", target_event_id="evt_1")

    def test_unrecordable_candidate_cannot_be_built(self) -> None:
        candidate = LearningCandidate(
            key="k", value="v", evidence=LearningEvidence.INFERENCE
        )
        with self.assertRaises(ValueError):
            candidate_to_feedback(
                candidate, user_id="usr_a", target_event_id="evt_1"
            )


class PersonalizedInsightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)

    def ask(self, provider_text: str, question: str = "Which backend language should I use?",
            **kwargs):
        provider = ScriptedProvider(provider_text)
        self.service._understanding = LLMGateway(
            provider, fallback=HeuristicProvider(), timeout_seconds=5.0
        )
        return provider, self.service.personalized_insight(
            "usr_a", question, target_event_id=kwargs.pop("target_event_id", "evt_1"), **kwargs
        )

    def test_structured_provider_answer_is_returned(self) -> None:
        self.service.record_preference(
            "usr_a", name="backend_language", value="TypeScript", domain="language"
        )
        provider, insight = self.ask(
            json.dumps(
                {
                    "answer": "Use TypeScript, you prefer it for backend work.",
                    "confidence": 0.8,
                    "used_context": True,
                    "candidates": [],
                }
            )
        )
        self.assertEqual(insight.provider, "scripted")
        self.assertFalse(insight.fallback_used)
        self.assertIn("TypeScript", insight.answer)
        self.assertGreaterEqual(insight.context_fact_count, 1)
        self.assertIn("CURRENT REQUEST", provider.seen[0].user)

    def test_malformed_provider_output_falls_back_to_brain_context(self) -> None:
        self.service.record_preference(
            "usr_a", name="backend_language", value="TypeScript", domain="language"
        )
        _, insight = self.ask("this is not json")
        self.assertTrue(insight.fallback_used)
        self.assertEqual(insight.provider, "context-only")
        self.assertIn("TypeScript", insight.answer)
        self.assertIn("no language model", insight.answer)

    def test_provider_failure_falls_back_without_raising(self) -> None:
        self.service.record_preference(
            "usr_a", name="backend_language", value="Rust", domain="language"
        )

        class BrokenProvider(LLMProvider):
            name = "broken"

            def complete(self, request: LLMRequest) -> str:
                raise LLMProviderError("upstream is down")

        self.service._understanding = LLMGateway(BrokenProvider(), timeout_seconds=1.0)
        insight = self.service.personalized_insight(
            "usr_a", "language?", target_event_id="evt_1"
        )
        self.assertTrue(insight.fallback_used)
        self.assertIn("Rust", insight.answer)

    def test_evidence_backed_candidate_reaches_the_learning_engine(self) -> None:
        _, insight = self.ask(
            json.dumps(
                {
                    "answer": "Noted.",
                    "confidence": 0.7,
                    "used_context": True,
                    "candidates": [
                        {
                            "kind": "preference",
                            "key": "backend_language",
                            "value": "TypeScript",
                            "evidence": "explicit_user_statement",
                            "confidence": 0.95,
                            "preference_domain": "language",
                        },
                        {
                            "kind": "preference",
                            "key": "editor",
                            "value": "Neovim",
                            "evidence": "inference",
                            "confidence": 0.4,
                        },
                    ],
                }
            )
        )
        recorded = {item.key: item for item in insight.recorded_candidates}
        self.assertTrue(recorded["backend_language"].recorded)
        self.assertIn("explicit", recorded["backend_language"].reason)
        self.assertFalse(recorded["editor"].recorded)
        # An explicit statement takes the explicit preference path, so it is
        # stored as a preference rather than as a feedback trace.
        stored = {p.name: p.value for p in self.service.preferences("usr_a")}
        self.assertEqual(stored.get("backend_language"), "TypeScript")
        self.assertEqual(self.service.feedback_history("usr_a"), [])

    def test_implicit_candidate_produces_feedback_evidence(self) -> None:
        _, insight = self.ask(
            json.dumps(
                {
                    "answer": "ok",
                    "confidence": 0.5,
                    "used_context": False,
                    "candidates": [
                        {
                            "kind": "preference",
                            "key": "test_runner",
                            "value": "pytest",
                            "evidence": "repeated_acceptance",
                            "confidence": 0.6,
                            "preference_domain": "testing",
                        }
                    ],
                }
            )
        )
        self.assertTrue(insight.recorded_candidates[0].recorded)
        self.assertIn("Learning Engine", insight.recorded_candidates[0].reason)
        self.assertEqual(len(self.service.feedback_history("usr_a")), 1)
        # Behaviour is not a statement: it does not become a preference yet.
        self.assertEqual(self.service.preferences("usr_a"), [])

    def test_learning_can_be_disabled(self) -> None:
        _, insight = self.ask(
            json.dumps(
                {
                    "answer": "ok",
                    "confidence": 0.5,
                    "used_context": False,
                    "candidates": [
                        {
                            "kind": "preference",
                            "key": "k",
                            "value": "v",
                            "evidence": "explicit_user_statement",
                            "confidence": 0.9,
                        }
                    ],
                }
            ),
            record_learning=False,
        )
        self.assertEqual(insight.recorded_candidates, [])
        self.assertEqual(self.service.feedback_history("usr_a"), [])

    def test_missing_target_event_id_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            self.service.personalized_insight("usr_a", "hi", target_event_id="  ")

    def test_empty_question_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            self.service.personalized_insight("usr_a", "  ", target_event_id="evt_1")

    def test_no_new_api_method_was_added(self) -> None:
        from contracts.api.methods import ApiMethod

        self.assertNotIn("personalized_insight", [m.value for m in ApiMethod])


class ExplicitPrecedenceAcrossProviderTests(unittest.TestCase):
    def test_explicit_preference_survives_a_learned_provider_candidate(self) -> None:
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        service.record_preference(
            "usr_a", name="backend_language", value="Rust", domain="language"
        )
        # The provider suggests something different, with real evidence.
        provider = ScriptedProvider(
            json.dumps(
                {
                    "answer": "switching to python",
                    "confidence": 0.6,
                    "used_context": False,
                    "candidates": [
                        {
                            "kind": "preference",
                            "key": "backend_language",
                            "value": "Python",
                            "evidence": "repeated_acceptance",
                            "confidence": 0.6,
                            "preference_domain": "language",
                        }
                    ],
                }
            )
        )
        service._understanding = LLMGateway(provider, timeout_seconds=5.0)
        insight = service.personalized_insight(
            "usr_a", "which backend language?", target_event_id="evt_1"
        )
        self.assertTrue(insight.recorded_candidates[0].recorded)
        values = {p.name: p.value for p in service.preferences("usr_a")}
        self.assertEqual(values["backend_language"], "Rust")

    def test_repeated_accepted_candidate_eventually_learns_when_nothing_explicit(self) -> None:
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        for index in range(4):
            provider = ScriptedProvider(
                json.dumps(
                    {
                        "answer": "ok",
                        "confidence": 0.5,
                        "used_context": False,
                        "candidates": [
                            {
                                "kind": "preference",
                                "key": "test_runner",
                                "value": "pytest",
                                "evidence": "repeated_acceptance",
                                "confidence": 0.7,
                                "preference_domain": "testing",
                            }
                        ],
                    }
                )
            )
            service._understanding = LLMGateway(provider, timeout_seconds=5.0)
            service.personalized_insight(
                "usr_a", "run tests?", target_event_id=f"evt_{index}"
            )
        learned = {p.name: p.value for p in service.preferences("usr_a")}
        self.assertEqual(learned.get("test_runner"), "pytest")

    def test_candidate_without_a_domain_stays_evidence_not_a_preference(self) -> None:
        """The Brain never invents a preference domain on the model's behalf."""
        service = build_brain_service(":memory:")
        self.addCleanup(service.close)
        for index in range(4):
            provider = ScriptedProvider(
                json.dumps(
                    {
                        "answer": "ok",
                        "confidence": 0.5,
                        "used_context": False,
                        "candidates": [
                            {
                                "kind": "preference",
                                "key": "backend_language",
                                "value": "TypeScript",
                                "evidence": "repeated_acceptance",
                                "confidence": 0.7,
                            }
                        ],
                    }
                )
            )
            service._understanding = LLMGateway(provider, timeout_seconds=5.0)
            insight = service.personalized_insight(
                "usr_a", "backend language?", target_event_id=f"evt_{index}"
            )
            self.assertTrue(insight.recorded_candidates[0].recorded)
        self.assertEqual(service.preferences("usr_a"), [])
        self.assertEqual(len(service.feedback_history("usr_a")), 4)


if __name__ == "__main__":
    unittest.main()
