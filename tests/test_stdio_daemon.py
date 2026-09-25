"""Tests — Phase 8 Slice 3 Part B: stdio JSON-lines transport daemon.

Proves the transport is synchronous, deterministic and strictly fenced on
stdin/stdout (protocol-only), that ``BrainApi.handle`` stays the single request
entry point, that malformed input never terminates the daemon, and that Brain
events stream out as documented ``kind=event`` frames with user + correlation
metadata preserved end to end. All behaviour is exercised in-process through
``io.StringIO`` streams — no subprocess is spawned.
"""

from __future__ import annotations

import io
import json
import unittest

from contracts.api import ApiErrorCode, ApiMethod
from contracts.brain_events.events import BrainEventType

from core import (
    BrainApi,
    BrainService,
    JsonLinesEventSink,
    StdioDaemon,
    build_brain_service,
)
from core.brain_events.sink import NullEventSink
from core.transport.stdio import default_json_line, event_frame, response_frame

from .ingestion_support import make_event


def _ping(request_id: str = "r1") -> str:
    return json.dumps({"id": request_id, "method": "ping"}) + "\n"


def _ingest(
    event_id: str = "evt_1",
    user: str = "usr_a",
    *,
    description: str = "implement server side pagination",
    correlation_id: str | None = None,
) -> str:
    event = make_event(
        event_id=event_id,
        event_type="source.todo.task_created",
        user_id=user,
        payload={"description": description},
        correlation_id=correlation_id,
    )
    request = {
        "id": f"req_{event_id}",
        "method": "ingest",
        "params": {"event": event},
    }
    if correlation_id is not None:
        request["params"]["correlation_id"] = correlation_id
    return json.dumps(request) + "\n"


class StdioHarness:
    """In-process daemon over in-memory streams (no subprocess)."""

    def __init__(
        self,
        *lines: str,
        diagnostics: io.StringIO | None = None,
    ) -> None:
        self.stdin = io.StringIO("".join(lines))
        self.stdout = io.StringIO()
        self.diagnostics = diagnostics
        self.sink = JsonLinesEventSink(self.stdout)
        self.service = build_brain_service(":memory:", sink=self.sink)
        self.api = BrainApi(self.service)
        self.daemon = StdioDaemon(
            self.api,
            stdin=self.stdin,
            stdout=self.stdout,
            sink=self.sink,
            diagnostics=diagnostics,
        )

    def run(self) -> "StdioHarness":
        self.daemon.serve()
        return self

    def frames(self) -> list[dict]:
        return _frames(self.stdout.getvalue())


def _frames(stdout: str) -> list[dict]:
    parsed = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parsed.append(json.loads(line))
    return parsed


class RequestFlowTests(unittest.TestCase):
    def test_valid_request_writes_one_response_frame(self):
        harness = StdioHarness(_ping("a")).run()
        frames = harness.frames()
        self.assertEqual(len(frames), 1)
        frame = frames[0]
        self.assertEqual(frame["kind"], "response")
        payload = frame["payload"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["id"], "a")
        self.assertEqual(payload["method"], "ping")
        self.assertEqual(payload["result"]["service"], "digital-brain")
        self.assertEqual(harness.daemon.request_count, 1)

    def test_multiple_requests_get_one_response_each_in_order(self):
        harness = StdioHarness(_ping("one"), _ping("two"), _ping("three")).run()
        frames = harness.frames()
        self.assertEqual(len(frames), 3)
        self.assertTrue(all(f["kind"] == "response" for f in frames))
        self.assertEqual(
            [f["payload"]["id"] for f in frames], ["one", "two", "three"]
        )

    def test_trailing_whitespace_still_parses(self):
        harness = StdioHarness('{"id": "w", "method": "ping"}   \n').run()
        frames = harness.frames()
        self.assertEqual(len(frames), 1)
        self.assertTrue(frames[0]["payload"]["ok"])


class ErrorHandlingTests(unittest.TestCase):
    def test_malformed_json_is_a_structured_error_not_a_crash(self):
        harness = StdioHarness("{this is definitely {not json\n").run()
        frames = harness.frames()
        self.assertEqual(len(frames), 1)
        frame = frames[0]
        self.assertEqual(frame["kind"], "response")
        self.assertFalse(frame["payload"]["ok"])
        self.assertEqual(frame["payload"]["error"]["code"], "bad_request")
        self.assertIn("invalid JSON", frame["payload"]["error"]["message"])
        self.assertEqual(harness.daemon.request_count, 1)

    def test_non_object_json_is_a_typed_error(self):
        harness = StdioHarness('[1, 2, 3]\n').run()
        frames = harness.frames()
        self.assertEqual(len(frames), 1)
        self.assertFalse(frames[0]["payload"]["ok"])
        self.assertEqual(frames[0]["payload"]["error"]["code"], "bad_request")

    def test_invalid_api_request_returns_typed_bad_request(self):
        # id as a non-string fails ApiRequest validation inside BrainApi.
        harness = StdioHarness(json.dumps({"id": 123, "method": "ping"}) + "\n").run()
        frames = harness.frames()
        self.assertEqual(len(frames), 1)
        self.assertFalse(frames[0]["payload"]["ok"])
        self.assertEqual(frames[0]["payload"]["error"]["code"], "bad_request")

    def test_unknown_method_is_a_typed_error(self):
        harness = StdioHarness(
            json.dumps({"id": "1", "method": "no_such_method"}) + "\n"
        ).run()
        self.assertEqual(
            harness.frames()[0]["payload"]["error"]["code"], "unknown_method"
        )

    def test_unsupported_version_is_a_typed_error(self):
        harness = StdioHarness(
            json.dumps({"id": "1", "method": "ping", "version": "v2"}) + "\n"
        ).run()
        self.assertEqual(
            harness.frames()[0]["payload"]["error"]["code"], "version_unsupported"
        )

    def test_validation_error_is_a_typed_error(self):
        harness = StdioHarness(
            json.dumps({"id": "1", "method": "understand", "params": {}}) + "\n"
        ).run()
        self.assertEqual(
            harness.frames()[0]["payload"]["error"]["code"], "validation_error"
        )


class ExplodingService(BrainService):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def ingest(self, data, *, correlation_id=None):  # noqa: D102
        raise RuntimeError("secret-token-stdio")

    def close(self) -> None:
        self.closed = True
        super().close()


class BoundaryTests(unittest.TestCase):
    def test_internal_error_never_leaks_message_or_traceback(self):
        api = BrainApi(ExplodingService())
        stdout = io.StringIO()
        daemon = StdioDaemon(
            api,
            stdin=io.StringIO(
                json.dumps(
                    {"id": "i1", "method": "ingest", "params": {"event": make_event()}}
                )
                + "\n"
            ),
            stdout=stdout,
        )
        daemon.serve()
        text = stdout.getvalue()
        self.assertNotIn("secret-token-stdio", text)
        self.assertNotIn("Traceback", text)
        frames = _frames(text)
        self.assertEqual(len(frames), 1)
        payload = frames[0]["payload"]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "internal_error")
        self.assertEqual(payload["error"]["details"]["exception"], "RuntimeError")

    def test_eof_is_a_clean_shutdown_and_closes_the_service(self):
        service = ExplodingService()
        daemon = StdioDaemon(
            BrainApi(service),
            stdin=io.StringIO(_ping() + "\n"),
            stdout=io.StringIO(),
        )
        daemon.serve()
        self.assertTrue(service.closed)
        self.assertEqual(daemon.request_count, 1)

    def test_sink_defaults_to_null_when_not_injected(self):
        daemon = StdioDaemon(
            BrainApi(build_brain_service(":memory:")),
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )
        self.assertIsInstance(daemon.sink, NullEventSink)

    def test_daemon_survives_mixed_malformed_and_valid_input(self):
        messages = [
            "{oops\n",
            json.dumps([1, 2, 3]) + "\n",
            _ping("ok1"),
            json.dumps({"id": "u1", "method": "nope"}) + "\n",
            json.dumps({"id": "v1", "method": "ping", "version": "v2"}) + "\n",
            json.dumps({"id": "w1", "method": "understand", "params": {}}) + "\n",
            "\n",
            "   \n",
        ]
        harness = StdioHarness(*messages).run()
        self.assertEqual(harness.daemon.request_count, 6)
        frames = harness.frames()
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[0]["payload"]["error"]["code"], "bad_request")
        self.assertEqual(frames[1]["payload"]["error"]["code"], "bad_request")
        self.assertTrue(frames[2]["payload"]["ok"])
        self.assertEqual(frames[2]["payload"]["id"], "ok1")
        self.assertEqual(frames[3]["payload"]["error"]["code"], "unknown_method")
        self.assertEqual(
            frames[4]["payload"]["error"]["code"], "version_unsupported"
        )
        self.assertEqual(
            frames[5]["payload"]["error"]["code"], "validation_error"
        )


class EventFlowTests(unittest.TestCase):
    def test_events_stream_as_event_frames_before_the_response(self):
        harness = StdioHarness(_ingest("evt_flow")).run()
        frames = harness.frames()
        self.assertEqual(len(frames) >= 2, True)
        event_frames = [f for f in frames if f["kind"] == "event"]
        response_frames = [f for f in frames if f["kind"] == "response"]
        self.assertTrue(event_frames)
        self.assertEqual(len(response_frames), 1)
        # Events emitted while the request ran come out before its response.
        self.assertEqual(frames[-1]["kind"], "response")
        self.assertEqual(
            {f["payload"]["type"] for f in event_frames},
            {BrainEventType.MEMORY_CREATED.value},
        )
        for frame in event_frames:
            payload = frame["payload"]
            self.assertEqual(payload["user_id"], "usr_a")
            self.assertIn("id", payload)
            self.assertIn("timestamp", payload)

    def test_response_and_event_frames_are_distinct(self):
        harness = StdioHarness(_ingest("evt_kind")).run()
        for frame in harness.frames():
            self.assertIn(frame["kind"], {"response", "event"})
            if frame["kind"] == "response":
                self.assertIn("ok", frame["payload"])
            else:
                self.assertIn(
                    frame["payload"]["type"],
                    {kind.value for kind in BrainEventType},
                )
                self.assertIn("user_id", frame["payload"])

    def test_correlation_id_survives_to_event_and_response(self):
        harness = StdioHarness(
            _ingest("evt_corr", correlation_id="corr-stdio-1")
        ).run()
        frames = harness.frames()
        event_payloads = [
            f["payload"]["payload"]
            for f in frames
            if f["kind"] == "event" and f["payload"]["type"] == "memory.created"
        ]
        self.assertTrue(event_payloads)
        for payload in event_payloads:
            self.assertEqual(payload.get("correlation_id"), "corr-stdio-1")
        response = [f for f in frames if f["kind"] == "response"][0]["payload"]
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["correlation_id"], "corr-stdio-1")

    def test_user_isolation_across_two_users(self):
        bob_event = make_event(
            event_id="evt_bob",
            event_type="source.calendar.event_created",
            user_id="usr_bob",
            payload={"summary": "sync with Ayxan"},
        )
        bob_event["subject"] = {"person_id": "per_1"}
        alice = _ingest("evt_alice", user="usr_alice")
        bob = json.dumps(
            {"id": "req_bob", "method": "ingest", "params": {"event": bob_event}}
        ) + "\n"
        summary_bob = json.dumps(
            {
                "id": "sum_bob",
                "method": "people_summary",
                "params": {"user_id": "usr_bob"},
            }
        ) + "\n"
        summary_alice = json.dumps(
            {
                "id": "sum_alice",
                "method": "people_summary",
                "params": {"user_id": "usr_alice"},
            }
        ) + "\n"
        harness = StdioHarness(bob, alice, summary_bob, summary_alice).run()
        for frame in harness.frames():
            if frame["kind"] != "event":
                continue
            if frame["payload"]["type"] == "memory.created":
                self.assertIn(
                    frame["payload"]["user_id"], {"usr_bob", "usr_alice"}
                )
        responses = [
            f["payload"] for f in harness.frames() if f["kind"] == "response"
        ]
        bob_summary = responses[2]["result"]["people"]
        alice_summary = responses[3]["result"]["people"]
        self.assertEqual(bob_summary[0]["person_id"], "per_1")
        self.assertEqual(alice_summary, [])

    def test_stdout_carries_only_protocol_frames(self):
        diagnostics = io.StringIO()
        harness = StdioHarness(
            "{oops\n",
            _ping("clean"),
            diagnostics=diagnostics,
        ).run()
        text = harness.stdout.getvalue()
        for line in text.splitlines():
            parsed = json.loads(line)
            self.assertIn(parsed["kind"], {"response", "event"})
        self.assertNotIn("Traceback", text)
        self.assertNotIn("shutdown", text)
        self.assertIn("shutdown:", diagnostics.getvalue())


class SerializationTests(unittest.TestCase):
    def test_default_json_line_is_deterministic_and_compact(self):
        left = {"kind": "event", "payload": {"z": 1, "a": [2, 1]}}
        right = {"payload": {"a": [2, 1], "z": 1}, "kind": "event"}
        self.assertEqual(default_json_line(left), default_json_line(right))
        self.assertEqual(default_json_line({"k": "v"}), '{"k":"v"}\n')

    def test_default_json_line_keeps_non_ascii(self):
        line = default_json_line({"message": "ə"})
        self.assertIn("ə", line)

    def test_response_frame_round_trips_as_a_response_envelope(self):
        api = BrainApi(build_brain_service(":memory:"))
        response = api.handle({"id": "rt", "method": "ping"})
        frame = response_frame(response)
        self.assertEqual(frame["kind"], "response")
        self.assertEqual(frame["payload"]["id"], "rt")
        self.assertTrue(frame["payload"]["ok"])

    def test_event_frame_round_trips_as_an_event_envelope(self):
        from contracts.brain_events.events import BrainEvent, BrainEventType

        event = BrainEvent(
            id="evt_frame",
            type=BrainEventType.MEMORY_CREATED,
            timestamp="2026-09-25T10:00:00Z",
            user_id="usr_a",
            source={"provider": "core", "component": "transport-test"},
            payload={"memory_id": "mem_1"},
        )
        frame = event_frame(event)
        self.assertEqual(frame["kind"], "event")
        self.assertEqual(frame["payload"]["type"], "memory.created")
        self.assertEqual(frame["payload"]["user_id"], "usr_a")

    def test_repeated_ping_serialization_is_byte_identical(self):
        harness = StdioHarness(_ping("same"), _ping("same")).run()
        frames = [f["payload"] for f in harness.frames()]
        self.assertEqual(json.dumps(frames[0], sort_keys=True),
                         json.dumps(frames[1], sort_keys=True))


if __name__ == "__main__":
    unittest.main()