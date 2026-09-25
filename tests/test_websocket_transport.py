"""Tests for the bounded, user-bound WebSocket Brain API transport."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from contracts.brain_events.events import BrainEvent, BrainEventType

from core import (
    BrainApi,
    WebSocketBrainServer,
    WebSocketBrainTransport,
    WebSocketEventRouter,
    WebSocketEventSink,
    WebSocketTransportError,
    build_brain_service,
)
from core.transport.websocket import (
    API_PATH,
    DEFAULT_EVENT_QUEUE_SIZE,
    MAX_MESSAGE_BYTES,
    _load_websockets_serve,
)

from .ingestion_support import make_event


def _brain_event(
    event_id: str = "evt_ws_1",
    user_id: str = "usr_a",
) -> BrainEvent:
    return BrainEvent(
        id=event_id,
        type=BrainEventType.MEMORY_CREATED,
        timestamp="2026-09-25T10:00:00Z",
        user_id=user_id,
        source={"provider": "core", "component": "websocket-test"},
        payload={"memory_id": "mem_ws_1", "correlation_id": "corr_ws_1"},
    )


def _ingest_request(
    event_id: str = "evt_ws_1",
    user_id: str = "usr_a",
) -> dict[str, Any]:
    event = make_event(
        event_id=event_id,
        event_type="source.todo.task_created",
        user_id=user_id,
        payload={"description": "implement WebSocket transport"},
        correlation_id="corr_ws_1",
    )
    return {
        "id": f"req_{event_id}",
        "method": "ingest",
        "params": {
            "event": event,
            "correlation_id": "corr_ws_1",
        },
    }


class _Request:
    def __init__(self, path: str) -> None:
        self.path = path


class FakeConnection:
    def __init__(
        self,
        messages: list[str | bytes] | None = None,
        *,
        path: str = f"{API_PATH}?user_id=usr_a",
        expected_sends: int = 0,
        request_style: bool = True,
        send_error: Exception | None = None,
    ) -> None:
        self.path = path
        if request_style:
            self.request = _Request(path)
        self._messages = list(messages or [])
        self._expected_sends = expected_sends
        self._expected = asyncio.Event()
        self._close_event = asyncio.Event()
        self._send_error = send_error
        self.sent: list[str] = []
        self.closed: tuple[int, str] | None = None

    def __aiter__(self) -> "FakeConnection":
        return self

    async def __anext__(self) -> str | bytes:
        if self._messages:
            return self._messages.pop(0)
        if self._expected_sends and len(self.sent) < self._expected_sends:
            expected_task = asyncio.create_task(self._expected.wait())
            close_task = asyncio.create_task(self._close_event.wait())
            try:
                await asyncio.wait(
                    {expected_task, close_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                expected_task.cancel()
                close_task.cancel()
                await asyncio.gather(
                    expected_task,
                    close_task,
                    return_exceptions=True,
                )
            if self._close_event.is_set() or not self._expected.is_set():
                raise StopAsyncIteration
        raise StopAsyncIteration

    async def send(self, message: str) -> None:
        if self._send_error is not None:
            raise self._send_error
        self.sent.append(message)
        if len(self.sent) >= self._expected_sends:
            self._expected.set()

    async def close(self, *, code: int, reason: str) -> None:
        self.closed = (code, reason)
        self._close_event.set()


class _Recorder:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


def _frames(raw: list[str]) -> list[dict[str, Any]]:
    return [json.loads(item) for item in raw]


def _server(
    *,
    event_queue_size: int = DEFAULT_EVENT_QUEUE_SIZE,
    origins: tuple[str | None, ...] = (None,),
) -> tuple[
    WebSocketBrainServer,
    WebSocketEventRouter,
    BrainApi,
]:
    router = WebSocketEventRouter()
    service = build_brain_service(":memory:", sink=router)
    api = BrainApi(service)
    server = WebSocketBrainServer(
        api,
        router,
        event_queue_size=event_queue_size,
        origins=origins,
    )
    return server, router, api


class WebSocketPathTests(unittest.TestCase):
    def setUp(self) -> None:
        router = WebSocketEventRouter()
        self.service = build_brain_service(":memory:", sink=router)
        self.transport = WebSocketBrainTransport(BrainApi(self.service))

    def tearDown(self) -> None:
        self.service.close()

    def test_valid_path_returns_user_id(self):
        self.assertEqual(
            self.transport.user_id_from_path(f"{API_PATH}?user_id=usr_a"),
            "usr_a",
        )
        self.assertEqual(
            self.transport.user_id_from_path(
                f"{API_PATH}?user_id=usr%20a"
            ),
            "usr a",
        )

    def test_missing_and_duplicate_user_id_are_rejected(self):
        for path in (
            API_PATH,
            f"{API_PATH}?user_id=",
            f"{API_PATH}?user_id=usr_a&user_id=usr_b",
        ):
            with self.subTest(path=path):
                with self.assertRaises(WebSocketTransportError):
                    self.transport.user_id_from_path(path)

    def test_invalid_path_and_query_are_rejected(self):
        for path in (
            "/v1/other?user_id=usr_a",
            f"/v1/brain/?user_id=usr_a",
            f"ws://localhost{API_PATH}?user_id=usr_a",
            f"{API_PATH}?user_id=usr_a&role=admin",
            f"{API_PATH}?user_id=%20usr_a%20",
            f"{API_PATH}?user_id=\ud800",
            f"{API_PATH}?user_id={'x' * 513}",
            f"{API_PATH}?user_id=usr_a&a=1&b=2&c=3&d=4",
            f"{API_PATH}?{'x' * 2_100}",
            f"{API_PATH}?user_id",
        ):
            with self.subTest(path=path):
                with self.assertRaises(WebSocketTransportError):
                    self.transport.user_id_from_path(path)


class WebSocketAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        router = WebSocketEventRouter()
        self.service = build_brain_service(":memory:", sink=router)
        self.transport = WebSocketBrainTransport(BrainApi(self.service))

    def tearDown(self) -> None:
        self.service.close()

    def test_text_and_binary_ping_use_brain_api(self):
        request = json.dumps({"id": "ping-1", "method": "ping"})
        text_response = self.transport.handle_message(request, "usr_a")
        binary_response = self.transport.handle_message(
            request.encode("utf-8"), "usr_a"
        )
        self.assertTrue(text_response.ok)
        self.assertEqual(text_response.id, "ping-1")
        self.assertTrue(binary_response.ok)
        self.assertEqual(
            text_response.model_dump(mode="json"),
            binary_response.model_dump(mode="json"),
        )

    def test_decode_failures_are_typed_bad_requests(self):
        cases = (
            ("{bad", "invalid JSON"),
            ("[1,2,3]", "JSON object"),
            (b"\xff", "UTF-8"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                response = self.transport.handle_message(raw, "usr_a")
                self.assertFalse(response.ok)
                self.assertEqual(response.error.code.value, "bad_request")
                self.assertIn(expected, response.error.message)
                self.assertEqual(response.error.source, "websocket")

    def test_direct_adapter_enforces_configured_message_limit(self):
        router = WebSocketEventRouter()
        service = build_brain_service(":memory:", sink=router)
        self.addCleanup(service.close)
        transport = WebSocketBrainTransport(
            BrainApi(service),
            max_message_bytes=16,
        )
        response = transport.handle_message(
            json.dumps({"id": "large", "method": "ping"}),
            "usr_a",
        )
        self.assertFalse(response.ok)
        self.assertIn("exceeds 16", response.error.message)
        with self.assertRaises(ValueError):
            WebSocketBrainTransport(BrainApi(service), max_message_bytes=0)

    def test_malformed_json_values_stay_inside_typed_boundary(self):
        unhashable_method = self.transport.handle_message(
            json.dumps({"id": "r", "method": []}),
            "usr_a",
        )
        self.assertEqual(
            unhashable_method.error.code.value,
            "unknown_method",
        )
        cases = (
            '{"id":"r","method":"ping","params":NaN}',
            '{"id":"r","method":"ping","params":{"value":1e999999}}',
            '{"id":"r","method":"ping","params":{"value":"\\ud800"}}',
            "[" * 2_000 + "]" * 2_000,
        )
        for raw in cases:
            with self.subTest(raw=raw[:40]):
                response = self.transport.handle_message(raw, "usr_a")
                self.assertFalse(response.ok)
                self.assertEqual(response.error.code.value, "bad_request")

    def test_existing_api_errors_keep_their_codes(self):
        cases = (
            ({"id": "r", "method": "missing"}, "unknown_method"),
            (
                {"id": "r", "method": "ping", "version": "v2"},
                "version_unsupported",
            ),
            (
                {"id": "r", "method": "understand", "params": {}},
                "validation_error",
            ),
        )
        for request, expected in cases:
            with self.subTest(expected=expected):
                response = self.transport.handle_message(
                    json.dumps(request), "usr_a"
                )
                self.assertEqual(response.error.code.value, expected)

    def test_connection_identity_rejects_cross_user_requests(self):
        cases = (
            {
                "id": "prefs",
                "method": "preferences",
                "params": {"user_id": "usr_b"},
            },
            _ingest_request("evt_cross_user", "usr_b"),
            {
                "id": "context",
                "method": "build_context",
                "params": {
                    "context": {
                        "user_id": "usr_b",
                        "repository": "digital-brain",
                    }
                },
            },
        )
        for request in cases:
            with self.subTest(method=request["method"]):
                response = self.transport.handle_message(
                    json.dumps(request), "usr_a"
                )
                self.assertFalse(response.ok)
                self.assertEqual(response.error.code.value, "bad_request")
                self.assertIn("does not match", response.error.message)

    def test_matching_nested_identity_reaches_api(self):
        response = self.transport.handle_message(
            json.dumps(_ingest_request("evt_matching", "usr_a")), "usr_a"
        )
        self.assertTrue(response.ok)
        self.assertEqual(response.result.user_id, "usr_a")

    def test_unexpected_api_exception_does_not_leak_details(self):
        api = self.transport.api

        def explode(message: Any) -> Any:
            raise RuntimeError("secret websocket token")

        api.handle = explode  # type: ignore[method-assign]
        response = self.transport.handle_message(
            json.dumps({"id": "boom", "method": "ping"}), "usr_a"
        )
        self.assertFalse(response.ok)
        self.assertEqual(response.error.code.value, "internal_error")
        self.assertEqual(
            response.error.details,
            {"exception": "RuntimeError"},
        )
        self.assertNotIn("secret", response.error.message)


class WebSocketEventSinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_frame_is_deterministic_and_writer_flushes(self):
        sink = WebSocketEventSink(2)
        sink.emit(_brain_event())
        await asyncio.sleep(0)
        recorder = _Recorder()
        writer = asyncio.create_task(sink.write_to(recorder))
        await sink.wait_until_flushed()
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)
        self.assertEqual(len(recorder.sent), 1)
        self.assertNotIn("\n", recorder.sent[0])
        frame = json.loads(recorder.sent[0])
        self.assertEqual(frame["kind"], "event")
        self.assertEqual(frame["payload"]["user_id"], "usr_a")
        self.assertEqual(
            frame["payload"]["payload"]["correlation_id"], "corr_ws_1"
        )

    async def test_non_ascii_event_is_serialized_as_safe_ascii_json(self):
        sink = WebSocketEventSink(2)
        event = _brain_event().model_copy(
            update={"payload": {"text": "Azərbaycan"}}
        )
        sink.emit(event)
        recorder = _Recorder()
        writer = asyncio.create_task(sink.write_to(recorder))
        await sink.wait_until_flushed()
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)
        self.assertTrue(recorder.sent[0].isascii())
        self.assertEqual(
            json.loads(recorder.sent[0])["payload"]["payload"]["text"],
            "Azərbaycan",
        )

    async def test_only_one_response_can_be_outstanding(self):
        router = WebSocketEventRouter()
        service = build_brain_service(":memory:", sink=router)
        self.addCleanup(service.close)
        response = BrainApi(service).handle({"id": "one", "method": "ping"})
        sink = WebSocketEventSink(2)
        recorder = _Recorder()
        writer = asyncio.create_task(sink.write_to(recorder))
        first = sink.enqueue_response(response)
        self.assertIsNotNone(first)
        self.assertIsNone(sink.enqueue_response(response))
        await first
        second = sink.enqueue_response(response)
        self.assertIsNotNone(second)
        await second
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)
        self.assertEqual(len(recorder.sent), 2)

    async def test_full_event_buffer_drops_newest_without_growing(self):
        sink = WebSocketEventSink(2)
        for index in range(3):
            sink.emit(_brain_event(f"evt_{index}"))
        await asyncio.sleep(0)
        self.assertEqual(sink.queued, 2)
        self.assertEqual(sink.accepted, 2)
        self.assertEqual(sink.dropped, 1)

    async def test_router_routes_only_to_matching_user_connections(self):
        alice_one = WebSocketEventSink(2)
        alice_two = WebSocketEventSink(2)
        bob = WebSocketEventSink(2)
        router = WebSocketEventRouter()
        router.register("usr_a", alice_one)
        router.register("usr_a", alice_two)
        router.register("usr_b", bob)
        router.emit(_brain_event(user_id="usr_a"))
        await asyncio.sleep(0)
        self.assertEqual(alice_one.queued, 1)
        self.assertEqual(alice_two.queued, 1)
        self.assertEqual(bob.queued, 0)
        self.assertEqual(router.connection_count, 3)
        router.unregister("usr_a", alice_one)
        self.assertEqual(router.connections_for_user("usr_a"), 1)
        router.emit(_brain_event("evt_2", "usr_b"))
        await asyncio.sleep(0)
        self.assertEqual(bob.queued, 1)
        self.assertEqual(alice_two.queued, 1)

    async def test_invalid_sink_input_and_registration_are_typed(self):
        sink = WebSocketEventSink(1)
        router = WebSocketEventRouter()
        router.register("usr_a", sink)
        with self.assertRaises(ValueError):
            router.register("usr_a", sink)
        with self.assertRaises(TypeError):
            router.register("usr_b", object())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            sink.emit(object())  # type: ignore[arg-type]
        for capacity in (0, -1, True):
            with self.assertRaises(ValueError):
                WebSocketEventSink(capacity)  # type: ignore[arg-type]


class WebSocketServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_and_event_frames_share_one_ordered_stream(self):
        server, router, api = _server()
        self.addCleanup(api.service.close)
        connection = FakeConnection(
            [json.dumps(_ingest_request())],
            expected_sends=2,
        )
        await server.handle_connection(connection)
        frames = _frames(connection.sent)
        self.assertEqual([frame["kind"] for frame in frames], ["event", "response"])
        self.assertEqual(frames[0]["payload"]["user_id"], "usr_a")
        self.assertTrue(frames[1]["payload"]["ok"])
        self.assertEqual(router.connection_count, 0)

    async def test_binary_request_gets_response_frame(self):
        server, _router, api = _server()
        self.addCleanup(api.service.close)
        request = json.dumps({"id": "binary", "method": "ping"}).encode("utf-8")
        connection = FakeConnection([request], expected_sends=1)
        await server.handle_connection(connection)
        frame = json.loads(connection.sent[0])
        self.assertEqual(frame["kind"], "response")
        self.assertEqual(frame["payload"]["id"], "binary")

    async def test_legacy_connection_path_attribute_is_supported(self):
        server, _router, api = _server()
        self.addCleanup(api.service.close)
        connection = FakeConnection(
            [json.dumps({"id": "legacy", "method": "ping"})],
            expected_sends=1,
            request_style=False,
        )
        await server.handle_connection(connection)
        self.assertTrue(json.loads(connection.sent[0])["payload"]["ok"])

    async def test_invalid_connection_identity_is_closed_as_policy_violation(self):
        server, router, api = _server()
        self.addCleanup(api.service.close)
        connection = FakeConnection(path=f"{API_PATH}?user_id=usr_a&user_id=usr_b")
        await server.handle_connection(connection)
        self.assertIsNotNone(connection.closed)
        self.assertEqual(connection.closed[0], 1008)
        self.assertEqual(connection.sent, [])
        self.assertEqual(router.connection_count, 0)

    async def test_shared_service_calls_are_serialized_across_connections(self):
        server, _router, api = _server()
        self.addCleanup(api.service.close)
        original = api.handle
        state_lock = threading.Lock()
        active = 0
        maximum = 0

        def serialized(message: Any) -> Any:
            nonlocal active, maximum
            with state_lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            try:
                return original(message)
            finally:
                with state_lock:
                    active -= 1

        api.handle = serialized  # type: ignore[method-assign]
        first = FakeConnection(
            [json.dumps({"id": "one", "method": "ping"})],
            expected_sends=1,
        )
        second = FakeConnection(
            [json.dumps({"id": "two", "method": "ping"})],
            expected_sends=1,
        )
        await asyncio.gather(
            server.handle_connection(first),
            server.handle_connection(second),
        )
        self.assertEqual(maximum, 1)
        self.assertEqual(len(first.sent), 1)
        self.assertEqual(len(second.sent), 1)

    async def test_writer_failure_closes_and_unregisters_connection(self):
        server, router, api = _server()
        self.addCleanup(api.service.close)
        connection = FakeConnection(
            [json.dumps({"id": "writer", "method": "ping"})],
            expected_sends=1,
            send_error=ConnectionError("private transport failure"),
        )
        await server.handle_connection(connection)
        self.assertIsNotNone(connection.closed)
        self.assertEqual(connection.closed[0], 1011)
        self.assertEqual(router.connection_count, 0)

    async def test_cancelled_handler_waits_for_shared_service_worker(self):
        server, _router, api = _server()
        self.addCleanup(api.service.close)
        original = api.handle
        first_started = threading.Event()
        release = threading.Event()
        state_lock = threading.Lock()
        calls = 0

        def blocking(message: Any) -> Any:
            nonlocal calls
            with state_lock:
                calls += 1
            first_started.set()
            release.wait(timeout=2)
            return original(message)

        api.handle = blocking  # type: ignore[method-assign]
        first = FakeConnection(
            [json.dumps({"id": "first", "method": "ping"})],
            expected_sends=1,
        )
        second = FakeConnection(
            [json.dumps({"id": "second", "method": "ping"})],
            expected_sends=1,
        )
        first_handler = asyncio.create_task(server.handle_connection(first))
        while not first_started.is_set():
            await asyncio.sleep(0)
        first_handler.cancel()
        second_handler = asyncio.create_task(server.handle_connection(second))
        await asyncio.sleep(0.02)
        self.assertEqual(calls, 1)
        release.set()
        await asyncio.gather(
            first_handler,
            second_handler,
            return_exceptions=True,
        )
        self.assertEqual(calls, 2)
        self.assertEqual(len(second.sent), 1)

    async def test_non_loopback_bind_requires_explicit_opt_in(self):
        server, _router, api = _server()
        self.addCleanup(api.service.close)
        with self.assertRaisesRegex(ValueError, "non-loopback"):
            await server.serve_forever("0.0.0.0", 0)
        with self.assertRaisesRegex(ValueError, "port"):
            await server.serve_forever("127.0.0.1", 70000)

    async def test_server_lifecycle_passes_bounded_library_options(self):
        server, _router, api = _server()
        self.addCleanup(api.service.close)
        captured: dict[str, Any] = {}

        class RunningServer:
            def __init__(self) -> None:
                self.closed = asyncio.Event()

            async def wait_closed(self) -> None:
                await self.closed.wait()

        running = RunningServer()

        class ServeContext:
            async def __aenter__(self) -> RunningServer:
                return running

            async def __aexit__(self, *args: Any) -> None:
                running.closed.set()

        def fake_serve(handler: Any, host: str, port: int, **kwargs: Any) -> ServeContext:
            captured.update(
                {
                    "handler": handler,
                    "host": host,
                    "port": port,
                    **kwargs,
                }
            )
            return ServeContext()

        with patch(
            "core.transport.websocket._load_websockets_serve",
            return_value=fake_serve,
        ):
            task = asyncio.create_task(server.serve_forever("127.0.0.1", 0))
            while server.server is None:
                await asyncio.sleep(0)
            server.stop()
            await asyncio.wait_for(task, timeout=1)
        self.assertEqual(captured["handler"], server.handle_connection)
        self.assertEqual(captured["host"], "127.0.0.1")
        self.assertEqual(captured["port"], 0)
        self.assertEqual(captured["max_size"], MAX_MESSAGE_BYTES)
        self.assertEqual(captured["max_queue"], 32)
        self.assertEqual(captured["origins"], (None,))

    async def test_server_requires_router_to_be_the_service_sink(self):
        router = WebSocketEventRouter()
        service = build_brain_service(":memory:", sink=router)
        self.addCleanup(service.close)
        with self.assertRaises(ValueError):
            WebSocketBrainServer(BrainApi(service), WebSocketEventRouter())
        with self.assertRaises(ValueError):
            WebSocketBrainServer(BrainApi(service), router, event_queue_size=0)
        with self.assertRaises(TypeError):
            WebSocketBrainServer(
                BrainApi(service),
                router,
                origins="https://example.test",
            )

    async def test_missing_optional_dependency_has_actionable_error(self):
        with patch(
            "core.transport.websocket.importlib.import_module",
            side_effect=ImportError("missing"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency"):
                _load_websockets_serve()


class WebSocketArchitectureTests(unittest.TestCase):
    def test_transport_does_not_import_internal_engines_or_database(self):
        path = (
            Path(__file__).resolve().parent.parent
            / "core"
            / "transport"
            / "websocket.py"
        )
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
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            lowered = stripped.lower()
            if any(token in lowered for token in forbidden):
                offenders.append(stripped)
        self.assertEqual(offenders, [])

    def test_public_module_import_does_not_require_websockets(self):
        module = __import__(
            "core.transport.websocket",
            fromlist=["WebSocketBrainServer"],
        )
        self.assertTrue(hasattr(module, "WebSocketBrainServer"))
        self.assertEqual(MAX_MESSAGE_BYTES, 1_000_000)


if __name__ == "__main__":
    unittest.main()
