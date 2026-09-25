"""Tests — Phase 8 Slice 2: Context + Learning → Reasoning feedback loop.

Proves: distilled Context reaches reasoning; empty/mismatched Context is valid
or rejected safely; learned profile (explicit rules, no invented data) reaches
reasoning and only suppresses exact avoided-topic keywords; user isolation;
determinism; unchanged default behavior without the new inputs; and that
Reasoning never touches a learning-state database directly.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from contracts.brain_events.events import BrainEventType
from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)

from core import build_brain_service
from core.context import Context, ContextStatus
from core.learning import LearningEngine, SqliteLearningStateRepository
from core.people import PeopleIntelligence
from core.reasoning import (
    ContextDistillationLimits,
    LearningInfluence,
    LearningProfilePort,
    ReasoningContext,
    ReasoningEngine,
    ReasoningResult,
    ReasoningValidationError,
    build_learning_influence,
    build_reasoning_context,
    context_keywords,
)

from .ingestion_support import make_event
from .memory_support import make_service
from .test_reasoning import make_context

FILES = [
    {
        "path": "web/list.py",
        "language": "python",
        "content": "def render():\n    return rows\n",
    }
]


def _dev(task="fix the pagination bug", user="usr_a"):
    return make_context(
        FILES,
        user_id=user,
        task=task,
        changed_files=["web/list.py"],
    )


def _seed_memories(svc, user="usr_a") -> None:
    svc.ingest(
        make_event(
            event_id="evt_p1",
            event_type="source.todo.task_created",
            user_id=user,
            payload={
                "description": "implement server side pagination for the list view"
            },
        )
    )
    svc.ingest(
        make_event(
            event_id="evt_p2",
            event_type="source.todo.task_created",
            user_id=user,
            payload={"description": "add pagination tests to the whole suite"},
        )
    )


def _service_with_avoidance(topic="pagination", rejections=2, user="usr_a"):
    svc = build_brain_service(":memory:")
    for i in range(rejections):
        svc.record_feedback(
            Feedback(
                feedback_id=f"fb_rej_{i}",
                user_id=user,
                source=FeedbackSource.PRODUCT,
                kind=FeedbackKind.EXPLICIT,
                target=FeedbackTarget(action_id="act_1"),
                label="rejected",
                value=-1.0,
                created_at=datetime.now(timezone.utc),
                correlation_id="corr_learn",
                metadata={"topic": topic, "action_type": "code.review"},
            )
        )
    return svc


def _blank_context(user="usr_a", context_id="ctx_blank") -> Context:
    return Context(
        context_id=context_id,
        user_id=user,
        status=ContextStatus.CURRENT_ONLY,
        created_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
    )


class _ExplodingContextEngine:
    """Context-engine stand-in whose build_context always raises.

    Lets tests prove BrainService degrades to ``None`` reasoning context
    instead of propagating engine failures.
    """

    def build_context(self, developer_context, *, task=None):
        raise RuntimeError("context store exploded")


class DistillationTests(unittest.TestCase):
    def setUp(self):
        self.svc = build_brain_service(":memory:")
        _seed_memories(self.svc)
        self.context = self.svc.build_context(_dev())

    def test_context_reaches_reasoning(self):
        rc = build_reasoning_context(self.context)
        self.assertIsInstance(rc, ReasoningContext)
        self.assertEqual(rc.user_id, "usr_a")
        self.assertTrue(rc.relevant_memories)
        self.assertEqual(rc.current_task, "fix the pagination bug")
        self.assertIn(rc.status, {"full", "current_only", "degraded"})
        self.assertTrue(
            any("pagination" in memory.content for memory in rc.relevant_memories)
        )

    def test_empty_context_remains_valid(self):
        rc = build_reasoning_context(_blank_context())
        self.assertEqual(rc.relevant_memories, [])
        self.assertEqual(rc.previous_bug_findings, [])
        self.assertEqual(rc.relevant_people, [])
        self.assertEqual(rc.user_id, "usr_a")
        result = ReasoningEngine().reason(_dev(), reasoning_context=rc)
        self.assertIs(result.context, rc)
        self.assertNotIn("pagination", result.intent.keywords)

    def test_distillation_is_deterministic(self):
        self.context.relevant_memories.reverse()
        first = build_reasoning_context(self.context)
        second = build_reasoning_context(self.context)
        self.assertEqual(first.model_dump(), second.model_dump())
        scores = [memory.score for memory in first.relevant_memories]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_distillation_respects_bounds(self):
        limits = ContextDistillationLimits(max_memories=1, content_chars=8)
        rc = build_reasoning_context(self.context, limits=limits)
        self.assertLessEqual(len(rc.relevant_memories), 1)
        for memory in rc.relevant_memories:
            self.assertLessEqual(len(memory.content), 8)
        self.assertLessEqual(len(rc.previous_bug_findings), limits.max_reference_ids)

    def test_rejects_non_context(self):
        with self.assertRaises(ReasoningValidationError):
            build_reasoning_context("not a context")  # type: ignore[arg-type]

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ReasoningValidationError):
            build_reasoning_context(
                self.context,
                limits=ContextDistillationLimits(max_memories=-1),
            )

    def test_context_keywords_only_distinct_signal(self):
        rc = build_reasoning_context(self.context)
        keywords = context_keywords(rc)
        self.assertIn("pagination", keywords)
        for keyword in keywords:
            self.assertEqual(keyword, keyword.lower())


class EngineContextTests(unittest.TestCase):
    def setUp(self):
        self.svc = build_brain_service(":memory:")
        _seed_memories(self.svc)
        self.rc = build_reasoning_context(self.svc.build_context(_dev()))

    def test_relevant_context_reaches_reasoning(self):
        result = ReasoningEngine().reason(
            _dev(), task="fix the pagination bug", reasoning_context=self.rc
        )
        self.assertIs(result.context, self.rc)
        self.assertIn("pagination", result.intent.keywords)

    def test_default_path_without_context_is_unchanged(self):
        result = ReasoningEngine().reason(_dev(), task="fix the pagination bug")
        self.assertIsNone(result.context)
        self.assertIsNone(result.learning)
        self.assertNotIn("pagination", result.intent.keywords)

    def test_user_mismatch_rejected(self):
        wrong = self.rc.model_copy(update={"user_id": "usr_b"})
        with self.assertRaises(ReasoningValidationError):
            ReasoningEngine().reason(_dev(), reasoning_context=wrong)

    def test_wrong_type_rejected(self):
        with self.assertRaises(ReasoningValidationError):
            ReasoningEngine().reason(_dev(), reasoning_context="nope")  # type: ignore[arg-type]

    def test_empty_reasoning_context_valid(self):
        rc = build_reasoning_context(_blank_context())
        result = ReasoningEngine().reason(_dev(), reasoning_context=rc)
        self.assertIs(result.context, rc)


class LearningInfluenceTests(unittest.TestCase):
    def test_learned_avoidance_suppresses_exact_keyword(self):
        svc = _service_with_avoidance("pagination", rejections=2)
        _seed_memories(svc)
        rc = build_reasoning_context(svc.build_context(_dev()))
        # control: no learning port -> context keyword present
        control = ReasoningEngine().reason(
            _dev(), task="fix the pagination bug", reasoning_context=rc
        )
        self.assertIn("pagination", control.intent.keywords)
        # wired service: learned avoidance suppresses the exact token
        result = svc.reason(_dev(), task="fix the pagination bug")
        self.assertIsNotNone(result.learning)
        assert result.learning is not None
        self.assertTrue(result.learning.has_profile)
        self.assertIn("pagination", result.learning.avoid_topics)
        self.assertNotIn("pagination", result.intent.keywords)

    def test_absent_profile_does_not_break_reasoning(self):
        svc = build_brain_service(":memory:")
        _seed_memories(svc)
        result = svc.reason(_dev(), task="fix the pagination bug")
        self.assertIsInstance(result, ReasoningResult)
        assert result.learning is not None
        self.assertFalse(result.learning.has_profile)
        self.assertEqual(result.learning.avoid_topics, [])
        self.assertEqual(result.learning.top_affinities, [])
        self.assertIsNone(result.learning.explanation_detail)
        self.assertEqual(result.learning.source_memory_ids, [])
        self.assertEqual(result.learning.feedback_count, 0)

    def test_user_isolation(self):
        svc = _service_with_avoidance("pagination", rejections=2)
        _seed_memories(svc)
        other = svc.reason(_dev(user="usr_b"))
        assert other.learning is not None
        self.assertFalse(other.learning.has_profile)
        self.assertEqual(other.learning.avoid_topics, [])
        self.assertEqual(other.user_id, "usr_b")

    def test_deterministic_influence(self):
        svc = _service_with_avoidance("pagination", rejections=2)
        _seed_memories(svc)
        first = svc.reason(_dev(), task="fix the pagination bug")
        second = svc.reason(_dev(), task="fix the pagination bug")
        assert first.learning is not None and second.learning is not None
        self.assertEqual(
            first.learning.model_dump(), second.learning.model_dump()
        )

    def test_blank_profile_yields_no_invented_data(self):
        profile = build_brain_service(":memory:").personalization_profile("usr_x")
        influence = build_learning_influence(profile)
        self.assertIsInstance(influence, LearningInfluence)
        self.assertFalse(influence.has_profile)
        self.assertEqual(influence.avoid_topics, [])
        self.assertEqual(influence.source_memory_ids, [])

    def test_avoidance_suppresses_exact_word_not_substring(self):
        svc = _service_with_avoidance(topic="sql", rejections=2)
        for event_id, description in {
            "evt_s1": "optimize the sql query for the mysql sharding endpoint",
            "evt_s2": "add a sql query helper and a mysql lookup cache",
        }.items():
            svc.ingest(
                make_event(
                    event_id=event_id,
                    event_type="source.todo.task_created",
                    user_id="usr_a",
                    payload={"description": description},
                )
            )

        rc = build_reasoning_context(
            svc.build_context(_dev(), task="tune the sql query for the mysql shard")
        )
        control = ReasoningEngine().reason(
            _dev(), task="tune the sql query", reasoning_context=rc
        )
        self.assertIn("sql", control.intent.keywords)
        self.assertIn("query", control.intent.keywords)
        self.assertIn("mysql", control.intent.keywords)

        result = svc.reason(_dev(), task="tune the sql query")
        assert result.learning is not None
        self.assertIn("sql", result.learning.avoid_topics)
        self.assertNotIn("sql", result.intent.keywords)
        self.assertIn("query", result.intent.keywords)
        self.assertIn("mysql", result.intent.keywords)


class PortAndIsolationTests(unittest.TestCase):
    def test_learning_engine_satisfies_port(self):
        memory = make_service()
        people = PeopleIntelligence(memory, writer=memory)
        engine = LearningEngine(
            memory,
            writer=memory,
            state=SqliteLearningStateRepository(":memory:"),
            people=people,
        )
        self.assertIsInstance(engine, LearningProfilePort)

    def test_reasoning_never_touches_learning_state_db(self):
        here = Path(__file__).resolve().parent.parent / "core" / "reasoning"
        offenders = []
        for path in here.glob("*.py"):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or
                        stripped.startswith("from ")):
                    continue
                lowered = stripped.lower()
                if "sqlite" in lowered or "learningstaterepository" in lowered:
                    offenders.append(f"{path.name}:{stripped}")
        self.assertEqual(offenders, [])

    def test_core_context_never_imports_reasoning(self):
        here = Path(__file__).resolve().parent.parent / "core" / "context"
        offenders = []
        for path in here.glob("*.py"):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or
                        stripped.startswith("from ")):
                    continue
                if "reasoning" in stripped.lower():
                    offenders.append(f"{path.name}:{stripped}")
        self.assertEqual(offenders, [])


class BrainServiceFlowTests(unittest.TestCase):
    def test_analyze_developer_wires_context_profile_reasoning(self):
        svc = _service_with_avoidance("pagination", rejections=2)
        _seed_memories(svc)
        outcome = svc.analyze_developer(_dev(), task="fix the pagination bug")
        self.assertIsNotNone(outcome.reasoning.context)
        assert outcome.reasoning.context is not None
        self.assertTrue(
            any(
                "pagination" in memory.content
                for memory in outcome.reasoning.context.relevant_memories
            )
        )
        assert outcome.reasoning.learning is not None
        self.assertTrue(outcome.reasoning.learning.has_profile)
        self.assertIn("pagination", outcome.reasoning.learning.avoid_topics)

        allowed = {
            BrainEventType.DEVELOPER_BUG_DETECTED,
            BrainEventType.DEVELOPER_FIX_PROPOSED,
            BrainEventType.DEVELOPER_TEST_RESULT,
            BrainEventType.DEVELOPER_REVIEW_FINDING,
            BrainEventType.DEVELOPER_DEPLOY_PROPOSED,
            BrainEventType.DECISION_CREATED,
            BrainEventType.ACTION_PROPOSED,
        }
        self.assertLessEqual({e.type for e in outcome.events}, allowed)

    def test_reason_read_path_produces_no_events(self):
        svc = build_brain_service(":memory:")
        _seed_memories(svc)
        svc.sink.clear()
        result = svc.reason(_dev(), task="fix the pagination bug")
        self.assertIsInstance(result, ReasoningResult)
        self.assertIsNotNone(result.context)
        self.assertEqual(svc.emitted, [])

    def test_context_engine_failure_degrades_to_none(self):
        svc = build_brain_service(":memory:")
        svc._context = _ExplodingContextEngine()
        outcome = svc.analyze_developer(_dev(), task="fix the pagination bug")
        self.assertIsNone(outcome.reasoning.context)
        self.assertIsInstance(outcome.reasoning, ReasoningResult)
        self.assertEqual(outcome.reasoning.user_id, "usr_a")
        self.assertEqual(outcome.reasoning.files_scanned, len(FILES))

    def test_context_user_isolation_at_brain_service_level(self):
        svc = build_brain_service(":memory:")
        _seed_memories(svc, user="usr_a")
        svc.ingest(
            make_event(
                event_id="evt_b1",
                event_type="source.todo.task_created",
                user_id="usr_b",
                payload={
                    "description": "add breadcrumb navigation to the shared shell"
                },
            )
        )
        result = svc.reason(
            _dev(user="usr_b"), task="look at the breadcrumb feature"
        )
        assert result.context is not None
        self.assertEqual(result.context.user_id, "usr_b")
        self.assertTrue(result.context.relevant_memories)
        self.assertTrue(
            any(
                "breadcrumb" in memory.content
                for memory in result.context.relevant_memories
            )
        )
        for memory in result.context.relevant_memories:
            self.assertNotIn("pagination", memory.content)
        self.assertNotIn("pagination", result.intent.keywords)

    def test_pipeline_context_passthrough(self):
        from core.brain_events import DevModePipeline

        svc = build_brain_service(":memory:")
        _seed_memories(svc)
        rc = build_reasoning_context(svc.build_context(_dev()))
        outcome = DevModePipeline().run(
            _dev(), task="fix the pagination bug", reasoning_context=rc
        )
        self.assertIs(outcome.reasoning.context, rc)
        self.assertIsNone(outcome.reasoning.learning)

    def test_pipeline_with_learning_alone(self):
        from core.brain_events import DevModePipeline

        memory = make_service()
        people = PeopleIntelligence(memory, writer=memory)
        learning = LearningEngine(
            memory,
            writer=memory,
            state=SqliteLearningStateRepository(":memory:"),
            people=people,
        )
        outcome = DevModePipeline(learning=learning).run(
            _dev(), task="look around"
        )
        assert outcome.reasoning.learning is not None
        self.assertFalse(outcome.reasoning.learning.has_profile)
        self.assertEqual(outcome.correlation_id, outcome.plan.correlation_id)


if __name__ == "__main__":
    unittest.main()