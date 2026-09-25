"""Tests for the Phase 8 Slice 1 BrainService application-service boundary.

Covers: real state transitions emit structured events; correlation_id and
user_id propagate end to end; user isolation; idempotency (no duplicate
events for a duplicate logical operation); invalid-input handling; and the
platform-independent guard (no UI/HTTP/device imports in the service layer).
"""

from __future__ import annotations

import inspect
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
from core.service.exceptions import BrainServiceValidationError
from core.understanding import DeveloperContext

from .ingestion_support import make_event
from .test_reasoning import make_context


def _feedback(user_id="usr_a", *, label="rejected", value=-1.0, feedback_id="fdb_1"):
    return Feedback(
        feedback_id=feedback_id,
        user_id=user_id,
        source=FeedbackSource.PRODUCT,
        kind=FeedbackKind.EXPLICIT,
        target=FeedbackTarget(memory_id="mem_1"),
        label=label,
        value=value,
        created_at=datetime.now(timezone.utc),
        correlation_id="corr_feedback",
        metadata={"action_type": "code.fix"},
    )


def _dev_context() -> DeveloperContext:
    return make_context(
        [
            {
                "path": "core/auth/login.py",
                "language": "python",
                "content": (
                    "def get_user():\n    return None\n\n"
                    "def render():\n    user = get_user()\n"
                    "    return user.email\n"
                ),
            }
        ],
        task="bug in login render",
        changed_files=["core/auth/login.py"],
        test_results=[
            {"name": "login", "status": "failed",
             "message": "Expected user object but received null"},
        ],
    )


class BrainServiceIngestTests(unittest.TestCase):
    def setUp(self):
        self.service = build_brain_service(":memory:")

    def test_ingest_emits_memory_created_with_ownership_and_correlation(self):
        result = self.service.ingest(
            make_event(event_type="source.linkedin.profile_updated"),
            correlation_id="corr_entry",
        )
        created = [
            e for e in self.service.emitted
            if e.type == BrainEventType.MEMORY_CREATED
        ]
        self.assertEqual(len(created), 1)
        event = created[0]
        self.assertEqual(event.user_id, result.user_id)
        self.assertEqual(event.payload["correlation_id"], "corr_entry")
        self.assertEqual(event.payload["memory_id"], result.memory_ids[0])
        for key in ("memory_id", "type", "importance", "confidence", "status"):
            self.assertIn(key, event.payload)
        self.assertEqual(event.timestamp.tzinfo, timezone.utc)

    def test_duplicate_ingest_is_idempotent_no_duplicate_events(self):
        data = make_event(event_type="source.linkedin.profile_updated")
        first = self.service.ingest(data)
        second = self.service.ingest(data)
        self.assertEqual(first.outcome.value, "accepted")
        self.assertEqual(second.outcome.value, "duplicate")
        created = [
            e for e in self.service.emitted
            if e.type == BrainEventType.MEMORY_CREATED
        ]
        self.assertEqual(len(created), 1)

    def test_invalid_input_rejected_before_side_effects(self):
        with self.assertRaises(BrainServiceValidationError):
            self.service.ingest("not a mapping")


class BrainServiceLearningTests(unittest.TestCase):
    def setUp(self):
        self.service = build_brain_service(":memory:")

    def test_record_feedback_emits_learning_signal(self):
        stored = self.service.record_feedback(_feedback())
        signals = [
            e for e in self.service.emitted
            if e.type == BrainEventType.LEARNING_SIGNAL_DETECTED
        ]
        self.assertEqual(len(signals), 1)
        event = signals[0]
        self.assertEqual(event.payload["signal"], "rejected")
        self.assertTrue(0.0 < event.payload["value"] <= 1.0)
        self.assertEqual(event.user_id, "usr_a")
        self.assertEqual(event.payload["correlation_id"], "corr_feedback")
        self.assertEqual(stored.signal.user_id, "usr_a")

    def test_repeated_rejection_emits_avoid_preference_update(self):
        for i in range(3):
            self.service.record_feedback(
                _feedback(feedback_id=f"fdb_{i}")
            )
        updated = [
            e for e in self.service.emitted
            if e.type == BrainEventType.PREFERENCE_UPDATED
        ]
        self.assertTrue(
            any(e.payload["preference"] == "avoid:suggestion:code.fix"
                for e in updated)
        )

    def test_invalid_feedback_rejected(self):
        with self.assertRaises(BrainServiceValidationError):
            self.service.record_feedback({"not": "feedback"})


class BrainServicePeopleTests(unittest.TestCase):
    def setUp(self):
        self.service = build_brain_service(":memory:")

    def test_record_preference_emits_preference_updated(self):
        pref = self.service.record_preference(
            "usr_a",
            name="concise explanations",
            value="preferred",
            domain="explanation_detail",
        )
        events = [
            e for e in self.service.emitted
            if e.type == BrainEventType.PREFERENCE_UPDATED
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["preference"], "concise explanations")
        self.assertEqual(events[0].user_id, "usr_a")
        self.assertEqual(events[0].payload["memory_id"], pref.memory_id)


class BrainServiceDeveloperTests(unittest.TestCase):
    def setUp(self):
        self.service = build_brain_service(":memory:")

    def test_analyze_developer_correlation_propagates_to_every_event(self):
        outcome = self.service.analyze_developer(
            _dev_context(),
            task="bug in login render",
            correlation_id="corr_devmode",
        )
        self.assertEqual(outcome.correlation_id, "corr_devmode")
        events = self.service.emitted
        # developer.* + decision.created + action.proposed
        self.assertGreaterEqual(len(events), 5)
        types = {e.type for e in events}
        self.assertIn(BrainEventType.DEVELOPER_BUG_DETECTED, types)
        self.assertIn(BrainEventType.DECISION_CREATED, types)
        self.assertIn(BrainEventType.ACTION_PROPOSED, types)
        for event in events:
            self.assertEqual(event.payload.get("correlation_id"), "corr_devmode")
            self.assertEqual(event.user_id, "usr_a")

    def test_analyze_developer_emits_plan_events_but_no_execution(self):
        outcome = self.service.analyze_developer(_dev_context())
        events = self.service.emitted
        decision_events = [
            e for e in events
            if e.type == BrainEventType.DECISION_CREATED
        ]
        self.assertEqual(len(decision_events), 1)
        self.assertEqual(decision_events[0].payload["action_count"],
                         len(outcome.plan.proposed_actions))
        for e in events:
            payload = e.payload
            self.assertNotIn("executed", payload)
            self.assertFalse(payload.get("auto_ship"))
        for action in outcome.plan.proposed_actions:
            self.assertFalse(hasattr(action, "execute"))
            self.assertFalse(hasattr(action, "executed_at"))

    def test_analyze_developer_invalid_context(self):
        with self.assertRaises(BrainServiceValidationError):
            self.service.analyze_developer(object())

    def test_build_context_read_surface(self):
        context = self.service.build_context(_dev_context())
        self.assertEqual(context.user_id, "usr_a")

    def test_build_context_invalid(self):
        with self.assertRaises(BrainServiceValidationError):
            self.service.build_context(object())


class BrainServiceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.service = build_brain_service(":memory:")

    def test_user_b_state_is_invisible_to_user_a(self):
        fdb = _feedback(user_id="usr_b", feedback_id="fdb_b")
        self.service.record_feedback(fdb)
        self.service.record_preference(
            "usr_b", name="concise", value="preferred"
        )
        # user A sees nothing of user B's learning / preferences
        self.assertEqual(self.service.learning_status("usr_a").signal_counts, {})
        self.assertEqual(self.service.feedback_history("usr_a"), [])
        self.assertEqual(self.service.preferences("usr_a"), [])
        # user B sees its own
        self.assertEqual(self.service.learning_status("usr_b").signal_counts["rejected"], 1)
        self.assertEqual(len(self.service.feedback_history("usr_b")), 1)
        self.assertEqual(len(self.service.preferences("usr_b")), 1)

    def test_emitted_events_scoped_by_user_ownership(self):
        self.service.record_preference(
            "usr_b", name="deploy early", value="preferred"
        )
        for event in self.service.emitted:
            self.assertEqual(event.user_id, "usr_b")

    def test_events_survive_json_round_trip(self):
        self.service.analyze_developer(_dev_context())
        for event in self.service.emitted:
            raw = event.model_dump_json()
            self.assertIn(event.type.value, raw)
            self.assertIn(event.user_id, raw)


class PlatformIndependenceTests(unittest.TestCase):
    FORBIDDEN = (
        "flask", "fastapi", "django", "aiohttp", "requests", "httpx",
        "urllib", "http.server", "socket", "websocket", "tkinter", "pyside",
        "pyqt", "electron", "react", "pygame", "asyncio", "kafka",
    )

    def _python_files(self):
        here = Path(__file__).resolve().parent.parent
        for folder in ("core/service", "core/brain_events"):
            yield from (here / folder).glob("*.py")

    def test_no_ui_http_or_device_imports_in_service_layer(self):
        offenders = []
        for path in self._python_files():
            text = path.read_text()
            for line in text.splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or
                        stripped.startswith("from ")):
                    continue
                lowered = stripped.lower()
                for token in self.FORBIDDEN:
                    if token in lowered:
                        offenders.append(f"{path.name}:{line.strip()}")
        self.assertEqual(offenders, [])

    def test_service_module_exports_no_transport_objects(self):
        import core.service as service_pkg

        names = {n for n, _ in inspect.getmembers(service_pkg)}
        self.assertTrue({"BrainService", "build_brain_service"} <= names)
        for name in names:
            self.assertNotIn(
                name.lower(),
                ("request", "response", "websocket", "http", "socket"),
            )


class ReadSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.service = build_brain_service(":memory:")
        self.service.record_preference(
            "usr_a", name="python first", value="preferred",
            domain="language", confidence=0.7, importance=0.5,
        )

    def test_preferences_and_developer_preferences_read(self):
        self.assertTrue(self.service.preferences("usr_a"))
        dev = self.service.developer_preferences("usr_a")
        self.assertIn("usr_a", dev.user_id)

    def test_understand_returns_validated_result(self):
        result = self.service.understand(
            "explain why the login render crashes", user_id="usr_a"
        )
        self.assertTrue(result.confidence >= 0.0)
        self.assertEqual(result.user_id, "usr_a")

    def test_missing_capability_raises_configuration_error(self):
        from core.service import BrainService
        from core.service.exceptions import BrainServiceConfigurationError

        empty = BrainService()
        with self.assertRaises(BrainServiceConfigurationError):
            empty.ingest(make_event())
        with self.assertRaises(BrainServiceConfigurationError):
            empty.learning_status("usr_a")


if __name__ == "__main__":
    unittest.main()