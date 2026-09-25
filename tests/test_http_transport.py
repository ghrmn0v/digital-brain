"""Tests — Phase 8 Slice 4A: minimal HTTP transport adapter.

Proves the HTTP layer is transport-only: every request routes through
``BrainApi.handle`` (the single entry point), the canonical ``ApiResponse``
envelope plus request id / version / correlation_id / user ownership survive,
existing API error codes map to a deterministic HTTP status, Brain events flow
through the service's own EventSink (no second event system), and the adapter
never imports database/engine internals directly.

Two layers are exercised: the adapter in-process with raw body bytes (no
sockets) and the real loopback server for HTTP semantics + lifecycle. No
network access outside localhost.
"""

from __future__ import annotations

import http.client
import json
import sqlite3
import unittest
from pathlib import Path

from contracts.api import (
    ApiError,
    ApiErrorCode,
    ApiMethod,
    error_response,
    ok_response,
)
from contracts.api import results as R
from contracts.brain_events.events import BrainEventType

from core import (
    BrainApi,
    HttpBrainHandler,
    HttpBrainServer,
    BrainService,
    HttpBrainTransport,
    build_brain_service,
    http_status_for,
)
from core.brain_events.sink import CollectingEventSink, NullEventSink
from core.memory import MemoryService, SqliteMemoryRepository

from .ingestion_support import make_event


def _make_transport(sink=None) -> HttpBrainTransport:
    service = build_brain_service(":memory:", sink=sink or NullEventSink())
    return HttpBrainTransport(BrainApi(service))


def _ping_body(request_id: str = "req_ping") -> bytes:
    return json.dumps({"id": request_id, "method": "ping"}).encode("utf-8")


def _ingest_body(
    event_id: str = "evt_h1",
    user: str = "usr_a",
    *,
    description: str = "implement persistent caching",
    correlation_id: str | None = None,
) -> bytes:
    event = make_event(
        event_id=event_id,
        event_type="source.todo.task_created",
        user_id=user,
        payload={"description": description},
        correlation_id=correlation_id,
    )
    request = {"id": f"req_{event_id}", "method": "ingest", "params": {"event": event}}
    if correlation_id is not None:
        request["params"]["correlation_id"] = correlation_id
    return json.dumps(request).encode("utf-8")


def _minimal_service() -> BrainService:
    """A BrainService with no faculty configured (drives not_configured)."""
    conn = sqlite3.connect(":memory:")
    memory = MemoryService(SqliteMemoryRepository(connection=conn))
    return BrainService(memory=memory)


class HttpTransportUnitTests(unittest.TestCase):
    """Adapter-level tests over raw body bytes — no sockets."""

    def test_health_is_static_and_contains_no_user_data(self):
        transport = _make_transport()
        payload = transport.health()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "digital-brain")
        self.assertEqual(
            set(payload), {"status", "service", "api_version"}
        )
        for value in payload.values():
            self.assertFalse(isinstance(value, dict) and bool(value))

    def test_valid_ping_returns_canonical_success(self):
        transport = _make_transport()
        payload, status = transport.handle_body(_ping_body("req-42"))
        self.assertEqual(status, 200)
        self.assertEqual(
            set(payload), {"id", "method", "version", "ok", "result", "error"}
        )
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["id"], "req-42")
        self.assertEqual(payload["method"], "ping")
        self.assertEqual(payload["version"], "v1")
        self.assertEqual(payload["result"]["service"], "digital-brain")

    def test_malformed_json_is_bad_request(self):
        transport = _make_transport()
        payload, status = transport.handle_body(b"{ this is not json")
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "bad_request")
        self.assertEqual(payload["error"]["source"], "http")

    def test_non_object_json_is_bad_request(self):
        transport = _make_transport()
        for body in (b'"just a string"', b"[1, 2, 3]"):
            payload, status = transport.handle_body(body)
            self.assertEqual(status, 400)
            self.assertEqual(payload["error"]["code"], "bad_request")

    def test_non_utf8_body_is_bad_request(self):
        transport = _make_transport()
        payload, status = transport.handle_body(b"\xff\xfe\x00")
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "bad_request")

    def test_missing_method_field_is_unknown_method(self):
        transport = _make_transport()
        body = json.dumps({"id": "req_missing"}).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "unknown_method")
        self.assertEqual(payload["id"], "req_missing")

    def test_unknown_method_is_404(self):
        transport = _make_transport()
        body = json.dumps({"id": "r", "method": "teleport"}).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "unknown_method")

    def test_invalid_params_is_422_validation_error(self):
        transport = _make_transport()
        body = json.dumps(
            {"id": "r", "method": "ping", "params": {"unexpected": True}}
        ).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 422)
        self.assertEqual(payload["error"]["code"], "validation_error")

    def test_unsupported_version_is_400(self):
        transport = _make_transport()
        body = json.dumps(
            {"id": "r", "method": "ping", "version": "v2"}
        ).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "version_unsupported")

    def test_extremely_long_unknown_method_is_canonical_http_error(self):
        transport = _make_transport()
        body = json.dumps(
            {"id": "r" * 5000, "method": "x" * 5000}
        ).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["code"], "unknown_method")
        self.assertLessEqual(len(payload["id"]), 128)
        self.assertLessEqual(len(payload["error"]["message"]), 2000)

    def test_extremely_long_unsupported_version_is_canonical_http_error(self):
        transport = _make_transport()
        body = json.dumps(
            {"id": "r", "method": "ping", "version": "v" * 5000}
        ).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "version_unsupported")
        self.assertLessEqual(len(payload["error"]["message"]), 2000)

    def test_canonical_error_response_shape(self):
        transport = _make_transport()
        body = json.dumps({"id": "r", "method": "teleport"}).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 404)
        self.assertEqual(
            set(payload), {"id", "method", "version", "ok", "result", "error"}
        )
        self.assertIsNone(payload["result"])
        self.assertEqual(
            set(payload["error"]), {"code", "message", "source", "details"}
        )

    def test_ingest_preserves_correlation_id(self):
        transport = _make_transport()
        payload, status = transport.handle_body(
            _ingest_body("evt_c1", "usr_a", correlation_id="corr_http_1")
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["result"]["correlation_id"], "corr_http_1")
        self.assertEqual(payload["result"]["user_id"], "usr_a")

    def test_not_configured_is_503(self):
        transport = HttpBrainTransport(BrainApi(_minimal_service()))
        body = json.dumps(
            {
                "id": "r",
                "method": "understand",
                "params": {"corpus": "hello world", "user_id": "usr_a"},
            }
        ).encode("utf-8")
        payload, status = transport.handle_body(body)
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "not_configured")

    def test_status_mapping_table(self):
        cases = [
            (ApiErrorCode.BAD_REQUEST, 400),
            (ApiErrorCode.UNKNOWN_METHOD, 404),
            (ApiErrorCode.VERSION_UNSUPPORTED, 400),
            (ApiErrorCode.VALIDATION_ERROR, 422),
            (ApiErrorCode.NOT_CONFIGURED, 503),
            (ApiErrorCode.INTERNAL_ERROR, 500),
        ]
        for code, expected in cases:
            with self.subTest(code=code.value):
                response = error_response(
                    "r", None, ApiError(code=code, message="boom")
                )
                self.assertEqual(http_status_for(response), expected)
        ok = ok_response("r", ApiMethod.PING, R.PingResult())
        self.assertEqual(http_status_for(ok), 200)

    def test_events_flow_through_service_sink_not_http(self):
        sink = CollectingEventSink()
        transport = _make_transport(sink)
        payload, status = transport.handle_body(
            _ingest_body("evt_e1", "usr_a", correlation_id="corr_evt_1")
        )
        self.assertEqual(status, 200)
        events = sink.by_user("usr_a")
        self.assertTrue(
            any(event.type == BrainEventType.MEMORY_CREATED for event in events)
        )
        self.assertIn("corr_evt_1", {event.payload.get("correlation_id") for event in events})


class HttpServerLifecycleTests(unittest.TestCase):
    """End-to-end over a real loopback server (localhost only)."""

    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.transport = HttpBrainTransport(BrainApi(self.service))
        self.server = HttpBrainServer(("127.0.0.1", 0), self.transport)
        self.thread = self.server.serve_in_thread()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.service.close()

    def _request(self, method: str, path: str, body: bytes | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read().decode("utf-8")
        conn.close()
        return response.status, raw

    def test_get_health_over_http(self):
        status, raw = self._request("GET", "/health")
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "digital-brain")

    def test_get_health_unknown_route_is_404(self):
        status, raw = self._request("GET", "/v1/other")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["error"], "not_found")

    def test_post_ping_over_http(self):
        status, raw = self._request("POST", "/v1/brain", _ping_body("req_over_http"))
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["id"], "req_over_http")
        self.assertEqual(payload["method"], "ping")
        self.assertEqual(payload["version"], "v1")

    def test_post_ping_unknown_route_is_404(self):
        status, raw = self._request("POST", "/v1/brainx", _ping_body())
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["error"], "not_found")

    def test_post_malformed_json_over_http(self):
        status, raw = self._request("POST", "/v1/brain", b"{ malformed")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(raw)["error"]["code"], "bad_request")

    def test_post_unknown_method_over_http(self):
        body = json.dumps({"id": "r", "method": "nope"}).encode("utf-8")
        status, raw = self._request("POST", "/v1/brain", body)
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(raw)["error"]["code"], "unknown_method")

    def test_user_isolation_through_http(self):
        status, _ = self._request(
            "POST",
            "/v1/brain",
            json.dumps(
                {
                    "id": "pref_a",
                    "method": "record_preference",
                    "params": {"user_id": "usr_a", "name": "editor-theme", "value": "dark"},
                }
            ).encode("utf-8"),
        )
        self.assertEqual(status, 200)

        _, raw_b = self._request(
            "POST",
            "/v1/brain",
            json.dumps(
                {"id": "pref_b", "method": "preferences", "params": {"user_id": "usr_b"}}
            ).encode("utf-8"),
        )
        payload_b = json.loads(raw_b)
        self.assertTrue(payload_b["ok"])
        self.assertEqual(payload_b["result"]["user_id"], "usr_b")
        self.assertEqual(payload_b["result"]["preferences"], [])

        _, raw_a = self._request(
            "POST",
            "/v1/brain",
            json.dumps(
                {"id": "pref_a2", "method": "preferences", "params": {"user_id": "usr_a"}}
            ).encode("utf-8"),
        )
        payload_a = json.loads(raw_a)
        self.assertTrue(payload_a["ok"])
        names = [p["name"] for p in payload_a["result"]["preferences"]]
        self.assertIn("editor-theme", names)

    def test_server_shuts_down_cleanly(self):
        self.assertIsInstance(self.server.transport, HttpBrainTransport)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive())


class ArchitectureGuardTests(unittest.TestCase):
    def test_http_transport_never_imports_internal_engines_or_db(self):
        here = Path(__file__).resolve().parent.parent / "core" / "transport" / "http.py"
        forbidden = (
            "sqlite",
            "core.context",
            "core.reasoning",
            "core.learning",
            "core.actions",
            "core.memory",
            "ContextEngine",
            "ReasoningEngine",
            "LearningEngine",
            "ActionPlanner",
        )
        offenders = []
        for line in here.read_text().splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            lowered = stripped.lower()
            if any(token in lowered for token in forbidden):
                offenders.append(stripped)
        self.assertEqual(offenders, [])

    def test_handler_importable_and_server_rejects_wrong_transport(self):
        self.assertIsNotNone(HttpBrainHandler)
        with self.assertRaises(TypeError):
            HttpBrainServer(("127.0.0.1", 0), None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()