"""Tests — Phase 8 Slice 3 Part A: typed client-facing Brain API contract.

Proves the wire contract (``contracts/api``) is strictly typed, deterministic,
JSON-round-trippable and transport-independent, that ``BrainApi`` maps every
method onto a real ``BrainService`` call (correlation/user preserved, nothing
executed), and that every failure path exits as a typed envelope response
(never a raised exception). The stdio JSON-lines daemon (Part B) consumes
exactly this ``BrainApi.handle`` surface.
"""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from contracts.api import (
    ApiErrorCode,
    ApiMethod,
    ApiRequest,
    ApiResponse,
    error_response,
    ok_response,
)
from contracts.api import params as P
from contracts.api import results as R
from contracts.brain_events.events import BrainEventType
from contracts.common.types import Source
from contracts.feedback.feedback import (
    Feedback,
    FeedbackKind,
    FeedbackSource,
    FeedbackTarget,
)

from core import BrainApi, BrainService, build_brain_service

from .ingestion_support import make_event

BUGGY_SOURCE = (
    "def get_user():\n"
    "    return None\n"
    "\n"
    "def render():\n"
    "    user = get_user()\n"
    "    print(user.email)\n"
)


def _dev_wire(
    user: str = "usr_a",
    task: str = "fix the null error in render",
    *,
    include_tests: bool = False,
) -> P.DeveloperSnapshotWire:
    return P.DeveloperSnapshotWire(
        user_id=user,
        repository="digital-brain",
        files=[
            P.DeveloperFileWire(
                path="core/auth/login.py",
                language="python",
                content=BUGGY_SOURCE,
            )
        ],
        changed_files=["core/auth/login.py"],
        current_file="core/auth/login.py",
        git_context=P.GitSnapshotWire(branch="main"),
        test_results=(
            [
                P.TestResultSnapshotWire(
                    name="test_login", status="failed", message="null"
                )
            ]
            if include_tests
            else []
        ),
        user_context={"task": task} if task else {},
    )


def _feedback(user: str = "usr_a", topic: str = "pagination", index: int = 0) -> Feedback:
    return Feedback(
        feedback_id=f"fdb_api_{index}",
        user_id=user,
        source=FeedbackSource.PRODUCT,
        kind=FeedbackKind.EXPLICIT,
        target=FeedbackTarget(action_id="act_1"),
        label="rejected",
        value=-1.0,
        created_at=datetime.now(timezone.utc),
        correlation_id="corr_api",
        metadata={"topic": topic, "action_type": "code.review"},
    )


class EnvelopeTests(unittest.TestCase):
    def test_request_rejects_unknown_fields(self):
        with self.assertRaises(ValidationError):
            ApiRequest.model_validate(
                {"id": "1", "method": "ping", "params": {}, "unexpected": 1}
            )

    def test_request_accepts_minimal_shape(self):
        request = ApiRequest.model_validate({"id": "1", "method": "ping"})
        self.assertEqual(request.method, ApiMethod.PING)
        self.assertEqual(request.version, "v1")
        self.assertEqual(request.params, {})

    def test_response_validates_ok_result_pair(self):
        with self.assertRaises(ValidationError):
            ApiResponse.model_validate({"id": "1", "method": "ping", "ok": True})
        with self.assertRaises(ValidationError):
            ApiResponse.model_validate(
                {"id": "1", "method": "ping", "ok": False}
            )
        with self.assertRaises(ValidationError):
            ApiResponse.model_validate(
                {
                    "id": "1",
                    "method": "ping",
                    "ok": True,
                    "result": R.PingResult(),
                    "error": {"code": "internal_error", "message": "x"},
                }
            )

    def test_builders_produce_valid_envelopes(self):
        ok = ok_response("1", ApiMethod.PING, R.PingResult())
        self.assertTrue(ok.ok)
        self.assertIsInstance(ok.result, R.PingResult)
        err = error_response(
            "1",
            ApiMethod.PING,
            {"code": "bad_request", "message": "boom"},
        )
        self.assertFalse(err.ok)
        self.assertEqual(err.error.code, ApiErrorCode.BAD_REQUEST)

    def test_json_round_trip(self):
        request = ApiRequest.model_validate(
            {"id": " 7 ", "method": "understand", "params": {"corpus": "hi"}}
        )
        rehydrated = ApiRequest.model_validate_json(request.model_dump_json())
        self.assertEqual(
            rehydrated.model_dump(mode="json"), request.model_dump(mode="json")
        )
        self.assertEqual(rehydrated.id, "7")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.api = BrainApi(build_brain_service(":memory:"))

    def test_ping_is_typed_and_ok(self):
        response = self.api.handle({"id": "a", "method": "ping"})
        self.assertTrue(response.ok)
        self.assertIsInstance(response.result, R.PingResult)
        self.assertEqual(response.result.service, "digital-brain")

    def test_describe_lists_every_method_and_schema(self):
        described = self.api.describe()
        self.assertEqual(described.version, "v1")
        self.assertEqual(len(described.methods), len(ApiMethod))
        for method in ApiMethod:
            self.assertIn(method.value, described.methods)
            schema = described.schemas[method.value]
            self.assertIn("params", schema)
            self.assertIn("result", schema)
            self.assertIn("properties", schema["params"])

    def test_describe_is_deterministic(self):
        first = self.api.describe().model_dump(mode="json")
        second = self.api.describe().model_dump(mode="json")
        self.assertEqual(first, second)


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.api = BrainApi(build_brain_service(":memory:"))

    def test_unknown_method_returns_typed_code(self):
        response = self.api.handle({"id": "1", "method": "definitely_not_a_method"})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.UNKNOWN_METHOD)

    def test_unsupported_version_returns_typed_code(self):
        response = self.api.handle({"id": "1", "method": "ping", "version": "v2"})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VERSION_UNSUPPORTED)

    def test_extremely_long_unknown_method_is_typed_and_bounded(self):
        response = self.api.handle({"id": "1", "method": "x" * 5000})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.UNKNOWN_METHOD)
        self.assertLessEqual(len(response.error.message), 2000)

    def test_extremely_long_unsupported_version_is_typed_and_bounded(self):
        response = self.api.handle(
            {"id": "1", "method": "ping", "version": "v" * 5000}
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VERSION_UNSUPPORTED)
        self.assertLessEqual(len(response.error.message), 2000)

    def test_malformed_long_method_does_not_raise_at_api_boundary(self):
        response = self.api.handle({"id": "1", "method": ["x"] * 2000})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.UNKNOWN_METHOD)
        self.assertLessEqual(len(response.error.message), 2000)

    def test_long_error_request_id_is_bounded(self):
        response = self.api.handle(
            {"id": "i" * 5000, "method": "x" * 5000}
        )
        self.assertFalse(response.ok)
        self.assertLessEqual(len(response.id), 128)
        self.assertTrue(response.id.endswith("..."))

    def test_long_validation_location_is_bounded(self):
        response = self.api.handle(
            {
                "id": "1",
                "method": "ping",
                "params": {"unexpected_" + "x" * 5000: True},
            }
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)
        self.assertLessEqual(len(response.error.message), 2000)

    def test_non_mapping_message_returns_bad_request(self):
        response = self.api.handle(None)  # type: ignore[arg-type]
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.BAD_REQUEST)

    def test_malformed_envelope_returns_bad_request(self):
        response = self.api.handle({"method": "ping"})
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.BAD_REQUEST)

    def test_to_json_message_is_json_serializable(self):
        message = self.api.to_json_message({"id": "9", "method": "describe"})
        self.assertIsInstance(json.loads(json.dumps(message)), dict)
        self.assertTrue(message["ok"])


class IngestAndWriteTests(unittest.TestCase):
    def setUp(self):
        self.svc = build_brain_service(":memory:")
        self.api = BrainApi(self.svc)

    def test_ingest_produces_memories_and_events(self):
        event = make_event(
            event_id="evt_api_1",
            event_type="source.todo.task_created",
            payload={"description": "implement server side pagination"},
            correlation_id="corr_ingest",
        )
        response = self.api.handle(
            {"id": "i1", "method": "ingest", "params": {"event": event,
                                                       "correlation_id": "corr_ingest"}}
        )
        self.assertTrue(response.ok, response.error)
        result = response.result
        self.assertEqual(result.outcome, "accepted")
        self.assertTrue(result.memory_ids)
        self.assertEqual(result.events_emitted, len(result.memory_ids))
        self.assertEqual(result.correlation_id, "corr_ingest")
        types = {event.type for event in self.svc.emitted}
        self.assertIn(BrainEventType.MEMORY_CREATED, types)

    def test_ingest_is_idempotent(self):
        event = make_event(
            event_id="evt_api_2",
            event_type="source.todo.task_created",
            payload={"description": "duplicate me"},
        )
        first = self.api.handle(
            {"id": "i2", "method": "ingest", "params": {"event": event}}
        )
        second = self.api.handle(
            {"id": "i3", "method": "ingest", "params": {"event": event}}
        )
        self.assertEqual(first.result.outcome, "accepted")
        self.assertEqual(second.result.outcome, "duplicate")
        self.assertFalse(second.result.memory_ids)
        self.assertEqual(second.result.duplicate_of_event_id, "evt_api_2")

    def test_ingest_outer_correlation_overrides_event_correlation(self):
        event = make_event(
            event_id="evt_api_corr",
            event_type="source.todo.task_created",
            payload={"description": "correlation precedence"},
            correlation_id="nested",
        )
        response = self.api.handle(
            {
                "id": "ic",
                "method": "ingest",
                "params": {
                    "event": event,
                    "correlation_id": "outer",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.correlation_id, "outer")
        self.assertTrue(self.svc.emitted)
        self.assertTrue(
            all(e.payload.get("correlation_id") == "outer" for e in self.svc.emitted)
        )

    def test_feedback_outer_correlation_updates_signal_and_event(self):
        response = self.api.handle(
            {
                "id": "fc",
                "method": "record_feedback",
                "params": {
                    "feedback": _feedback().model_dump(mode="json"),
                    "correlation_id": "outer",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.signal.correlation_id, "outer")
        self.assertTrue(self.svc.emitted)
        self.assertTrue(
            all(e.payload.get("correlation_id") == "outer" for e in self.svc.emitted)
        )

    def test_nested_correlation_remains_the_fallback(self):
        event = make_event(
            event_id="evt_api_corr_fallback",
            event_type="source.todo.task_created",
            payload={"description": "fallback correlation"},
            correlation_id="nested",
        )
        response = self.api.handle(
            {"id": "icf", "method": "ingest", "params": {"event": event}}
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.correlation_id, "nested")
        self.assertEqual(self.svc.emitted[-1].payload["correlation_id"], "nested")

    def test_invalid_ingest_params_validated(self):
        event = make_event(
            event_id="evt_api_3",
            event_type="source.linkedin.profile_updated",
        )
        del event["occurred_at"]
        response = self.api.handle(
            {"id": "i4", "method": "ingest", "params": {"event": event}}
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)

    def test_record_feedback_returns_typed_signal(self):
        response = self.api.handle(
            {
                "id": "f1",
                "method": "record_feedback",
                "params": {
                    "feedback": _feedback().model_dump(mode="json"),
                    "correlation_id": "corr_api",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        result = response.result
        self.assertEqual(result.user_id, "usr_a")
        self.assertEqual(result.signal.kind, "rejected")
        self.assertEqual(result.signal.source, "product")
        self.assertEqual(result.signal.topic, "pagination")
        self.assertEqual(result.signal.correlation_id, "corr_api")

    def test_record_preference_emits_preference_updated(self):
        response = self.api.handle(
            {
                "id": "p1",
                "method": "record_preference",
                "params": {
                    "user_id": "usr_a",
                    "name": "logging_detail",
                    "value": "brief",
                    "domain": "coding_style",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.domain, "coding_style")
        self.assertEqual(response.result.name, "logging_detail")
        types = {event.type for event in self.svc.emitted}
        self.assertIn(BrainEventType.PREFERENCE_UPDATED, types)


class RequestSourceTests(unittest.TestCase):
    def setUp(self):
        self.svc = build_brain_service(":memory:")
        self.addCleanup(self.svc.close)
        self.api = BrainApi(self.svc)
        self.source = Source(
            provider="pc", component="client", version="1"
        )

    def test_ingest_request_source_is_used_for_event_envelope(self):
        event = make_event(
            event_id="evt_source_ingest",
            event_type="source.todo.task_created",
            payload={"description": "source propagation"},
        )
        response = self.api.handle(
            {
                "id": "si",
                "method": "ingest",
                "source": self.source.model_dump(mode="json"),
                "params": {"event": event},
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(self.svc.emitted[0].source, self.source)

    def test_feedback_request_source_does_not_replace_feedback_source(self):
        response = self.api.handle(
            {
                "id": "sf",
                "method": "record_feedback",
                "source": self.source.model_dump(mode="json"),
                "params": {"feedback": _feedback().model_dump(mode="json")},
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.signal.source, "product")
        self.assertEqual(self.svc.emitted[0].source, self.source)

    def test_preference_request_source_is_used_for_event_envelope(self):
        response = self.api.handle(
            {
                "id": "sp",
                "method": "record_preference",
                "source": self.source.model_dump(mode="json"),
                "params": {
                    "user_id": "usr_a",
                    "name": "logging_style",
                    "value": "concise",
                    "domain": "coding_style",
                    "source": {"provider": "user", "component": "settings"},
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(self.svc.emitted[0].source, self.source)

    def test_developer_result_events_preserve_request_source(self):
        response = self.api.handle(
            {
                "id": "sd",
                "method": "analyze_developer",
                "source": self.source.model_dump(mode="json"),
                "params": {"context": _dev_wire().model_dump(mode="json")},
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertTrue(response.result.events)
        self.assertTrue(
            all(event.source == self.source for event in response.result.events)
        )


class DeveloperModeTests(unittest.TestCase):
    def setUp(self):
        self.svc = build_brain_service(":memory:")
        self.api = BrainApi(self.svc)

    def test_reason_returns_typed_wire(self):
        response = self.api.handle(
            {
                "id": "r1",
                "method": "reason",
                "params": {"context": _dev_wire().model_dump(mode="json")},
            }
        )
        self.assertTrue(response.ok, response.error)
        reasoning = response.result
        self.assertEqual(reasoning.user_id, "usr_a")
        self.assertEqual(reasoning.intent.intent_kind, "bug_detection")
        self.assertTrue(reasoning.context_used)
        self.assertTrue(reasoning.learning_used)
        self.assertIn("null", reasoning.intent.keywords)

    def test_reason_is_deterministic(self):
        params = {"context": _dev_wire().model_dump(mode="json")}
        first = self.api.handle({"id": "d1", "method": "reason", "params": params})
        second = self.api.handle({"id": "d2", "method": "reason", "params": params})
        self.assertEqual(
            first.result.intent.model_dump(mode="json"),
            second.result.intent.model_dump(mode="json"),
        )
        # Finding ids are freshly minted per pass, so determinism is about the
        # content and counts, not the random id suffixes.
        self.assertEqual(len(first.result.bugs), len(second.result.bugs))
        self.assertEqual(
            len(first.result.review_findings), len(second.result.review_findings)
        )
        self.assertEqual(first.result.files_scanned, second.result.files_scanned)
        self.assertEqual(first.result.total_changed, second.result.total_changed)
        self.assertEqual(first.result.context_used, second.result.context_used)
        self.assertEqual(first.result.learning_used, second.result.learning_used)

    def test_analyze_developer_full_flow(self):
        wire = _dev_wire(include_tests=True).model_dump(mode="json")
        response = self.api.handle(
            {
                "id": "a1",
                "method": "analyze_developer",
                "params": {
                    "context": wire,
                    "task": "fix the null error in render",
                    "correlation_id": "corr_dev",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        result = response.result
        self.assertEqual(result.user_id, "usr_a")
        self.assertEqual(result.correlation_id, "corr_dev")
        self.assertTrue(result.events)
        event_types = {event.type for event in result.events}
        self.assertIn(BrainEventType.DEVELOPER_BUG_DETECTED, event_types)
        self.assertIn(BrainEventType.DEVELOPER_FIX_PROPOSED, event_types)
        self.assertIn(BrainEventType.DEVELOPER_TEST_RESULT, event_types)
        # Nothing executes: proposals are pure data.
        for action in result.plan.proposed_actions:
            self.assertFalse(hasattr(action, "execute"))

    def test_analyze_developer_result_events_match_single_sink_delivery(self):
        response = self.api.handle(
            {
                "id": "a-events",
                "method": "analyze_developer",
                "params": {
                    "context": _dev_wire(include_tests=True).model_dump(mode="json")
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        result_events = response.result.events
        sink_events = self.svc.emitted
        self.assertEqual(result_events, sink_events)
        expected_tail = [BrainEventType.DECISION_CREATED] + [
            BrainEventType.ACTION_PROPOSED
        ] * len(response.result.plan.proposed_actions)
        self.assertEqual(
            [event.type for event in result_events[-len(expected_tail) :]],
            expected_tail,
        )
        self.assertEqual(
            len({event.id for event in result_events}), len(result_events)
        )

    def test_analyze_developer_preserves_explicit_empty_correlation(self):
        response = self.api.handle(
            {
                "id": "a-empty-correlation",
                "method": "analyze_developer",
                "params": {
                    "context": _dev_wire().model_dump(mode="json"),
                    "correlation_id": "",
                },
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.correlation_id, "")
        self.assertTrue(response.result.events)
        self.assertTrue(
            all(
                event.payload["correlation_id"] == ""
                for event in response.result.events
            )
        )

    def test_analyze_developer_events_owned_by_requested_user(self):
        wire = _dev_wire(user="usr_b").model_dump(mode="json")
        response = self.api.handle(
            {"id": "a2", "method": "analyze_developer", "params": {"context": wire}}
        )
        self.assertTrue(response.ok, response.error)
        for event in response.result.events:
            self.assertEqual(event.user_id, "usr_b")
        for event in self.svc.emitted:
            self.assertEqual(event.user_id, "usr_b")

    def test_analyze_developer_validates_params(self):
        response = self.api.handle(
            {"id": "a3", "method": "analyze_developer", "params": {}}
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)


class ReadSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.svc = build_brain_service(":memory:")
        self.api = BrainApi(self.svc)

    def test_build_context_returns_bounded_summary(self):
        response = self.api.handle(
            {
                "id": "c1",
                "method": "build_context",
                "params": {"context": _dev_wire().model_dump(mode="json")},
            }
        )
        self.assertTrue(response.ok, response.error)
        result = response.result
        self.assertEqual(result.user_id, "usr_a")
        self.assertEqual(result.status, "current_only")
        self.assertGreaterEqual(result.relevant_memory_count, 0)

    def test_understand_returns_typed_result(self):
        response = self.api.handle(
            {
                "id": "u1",
                "method": "understand",
                "params": {"corpus": "refactor the authentication module"},
            }
        )
        self.assertTrue(response.ok, response.error)
        result = response.result
        self.assertEqual(result.provider, "heuristic")
        self.assertFalse(result.fallback_used)
        self.assertTrue(0.0 < result.confidence <= 1.0)

    def test_preferences_roundtrip(self):
        self.api.handle(
            {
                "id": "p2",
                "method": "record_preference",
                "params": {
                    "user_id": "usr_a",
                    "name": "logging_detail",
                    "value": "brief",
                    "domain": "coding_style",
                },
            }
        )
        response = self.api.handle(
            {"id": "p3", "method": "preferences", "params": {"user_id": "usr_a"}}
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(response.result.domains, ["coding_style"])
        self.assertTrue(response.result.preferences)

    def test_developer_preferences_are_bucketed(self):
        self.api.handle(
            {
                "id": "p4",
                "method": "record_preference",
                "params": {
                    "user_id": "usr_a",
                    "name": "framework",
                    "value": "pytest",
                    "domain": "testing",
                },
            }
        )
        response = self.api.handle(
            {
                "id": "p5",
                "method": "developer_preferences",
                "params": {"user_id": "usr_a"},
            }
        )
        self.assertTrue(response.ok, response.error)
        self.assertEqual(len(response.result.testing), 1)
        self.assertEqual(response.result.testing[0].value, "pytest")

    def test_people_summary_after_person_event(self):
        event = make_event(
            event_id="evt_people_1",
            event_type="source.calendar.event_created",
            payload={"summary": "sync with Ayxan"},
            user_id="usr_a",
        )
        event["subject"] = {"person_id": "per_1"}
        self.api.handle({"id": "pp1", "method": "ingest", "params": {"event": event}})
        response = self.api.handle(
            {"id": "pp2", "method": "people_summary", "params": {"user_id": "usr_a"}}
        )
        self.assertTrue(response.ok, response.error)
        self.assertTrue(response.result.people)
        self.assertEqual(response.result.people[0].person_id, "per_1")

    def test_learning_reads_after_feedback(self):
        for index in range(2):
            self.api.handle(
                {
                    "id": f"fb_{index}",
                    "method": "record_feedback",
                    "params": {
                        "feedback": _feedback(topic="pagination", index=index).model_dump(mode="json")
                    },
                }
            )
        status = self.api.handle(
            {
                "id": "ls1",
                "method": "learning_status",
                "params": {"user_id": "usr_a"},
            }
        )
        self.assertTrue(status.ok, status.error)
        self.assertTrue(status.result.topics)
        self.assertIn("rejected", status.result.signal_counts)

        profile = self.api.handle(
            {
                "id": "lp1",
                "method": "personalization_profile",
                "params": {"user_id": "usr_a"},
            }
        )
        self.assertTrue(profile.ok, profile.error)
        self.assertEqual(profile.result.feedback_count, 2)

        history = self.api.handle(
            {
                "id": "fh1",
                "method": "feedback_history",
                "params": {"user_id": "usr_a", "limit": 10},
            }
        )
        self.assertTrue(history.ok, history.error)
        self.assertEqual(len(history.result.items), 2)
        self.assertEqual(history.result.items[0].kind, "rejected")


class ErrorMappingTests(unittest.TestCase):
    def setUp(self):
        self.api = BrainApi(BrainService())

    def test_missing_capability_maps_to_not_configured(self):
        response = self.api.handle(
            {"id": "nc1", "method": "preferences", "params": {"user_id": "usr_a"}}
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.NOT_CONFIGURED)

    def test_missing_required_params_map_to_validation(self):
        response = self.api.handle(
            {"id": "v1", "method": "understand", "params": {}}
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code, ApiErrorCode.VALIDATION_ERROR)


class PlatformIndependenceTests(unittest.TestCase):
    """The API contract and adapter never touch a transport or a socket."""

    FORBIDDEN_TOKENS = (
        "import http",
        "import socket",
        "import threading",
        "import asyncio",
        "websocket",
        "aiohttp",
        "subprocess",
    )

    def test_contracts_api_imports_no_transport_and_no_core(self):
        import contracts.api as api_package

        for module_info in pkgutil.iter_modules(api_package.__path__):
            module = importlib.import_module(
                f"contracts.api.{module_info.name}"
            )
            source = inspect.getsource(module)
            for token in self.FORBIDDEN_TOKENS:
                self.assertNotIn(token, source, f"{module.__name__} leaked {token}")
            self.assertNotIn("import core", source)

    def test_adapter_imports_no_transport(self):
        from core.service import api as adapter

        source = inspect.getsource(adapter)
        for token in self.FORBIDDEN_TOKENS:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()