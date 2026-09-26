"""Bounded, user-bound WebSocket transport for the Brain API.

This module adapts one bidirectional WebSocket connection to the existing
``BrainApi.handle`` and ``EventSink`` boundaries. Incoming text or binary
messages are JSON ``ApiRequest`` objects; outgoing responses and Brain events
reuse the stdio frame envelope so one socket has one deterministic wire format.

The server binds a connection to one ``user_id`` from ``/v1/brain?user_id=...``.
Request ownership fields must match that connection identity, and the event
router sends each event only to sockets bound to the event's user. This is
isolation and routing metadata, not authentication. The default server remains
loopback-only and accepts clients without an Origin header while rejecting
browser origins unless they are explicitly allowed.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import ipaddress
import json
import math
import sys
import threading
from collections import deque
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

from contracts.api import (
    ApiError,
    ApiErrorCode,
    ApiMethod,
    ApiResponse,
    error_response,
    event_frame,
    response_frame,
)
from contracts.brain_events.events import BrainEvent

from core.service.api import BrainApi
from core.config import resolve_llm_provider
from core.service.brain_service import build_brain_service

API_PATH = "/v1/brain"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
DEFAULT_EVENT_QUEUE_SIZE = 128
DEFAULT_LIBRARY_QUEUE_SIZE = 32
MAX_MESSAGE_BYTES = 1_000_000
MAX_PATH_CHARS = 2_048
MAX_QUERY_FIELDS = 4
_MAX_USER_ID_LENGTH = 512
_MAX_CLOSE_REASON_BYTES = 123


class WebSocketTransportError(RuntimeError):
    """A WebSocket connection cannot be admitted safely."""


class WebSocketSendConnection(Protocol):
    """Minimal connection surface used by the event writer."""

    async def send(self, message: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _OutboundFrame:
    text: str
    is_event: bool


def _wire_text(frame: Mapping[str, Any]) -> str:
    return json.dumps(
        frame,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _valid_user_id(value: Any) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= _MAX_USER_ID_LENGTH:
        return False
    if value != value.strip():
        return False
    return not any(
        ord(character) < 32
        or ord(character) == 127
        or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    )


def _bounded_request_id(value: Any) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return text if len(text) <= 128 else text[:125] + "..."


def _connection_path(connection: Any) -> str:
    request = getattr(connection, "request", None)
    path = getattr(request, "path", None)
    if path is None:
        path = getattr(connection, "path", None)
    if not isinstance(path, str):
        raise WebSocketTransportError("WebSocket connection path is unavailable")
    return path


def _is_loopback_host(host: str) -> bool:
    if host.strip().lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("JSON number is not finite")
    return parsed


def _validate_unicode(value: Any) -> None:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise ValueError("JSON contains an unpaired surrogate")
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())


class WebSocketBrainTransport:
    """Transport-only decoder and identity guard over one ``BrainApi``."""

    def __init__(
        self,
        api: BrainApi,
        *,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        if not isinstance(api, BrainApi):
            raise TypeError("WebSocketBrainTransport requires a BrainApi")
        if (
            isinstance(max_message_bytes, bool)
            or not isinstance(max_message_bytes, int)
            or max_message_bytes < 1
        ):
            raise ValueError("max_message_bytes must be a positive integer")
        self._api = api
        self._max_message_bytes = max_message_bytes

    @property
    def api(self) -> BrainApi:
        return self._api

    def user_id_from_path(self, path: str) -> str:
        """Validate ``/v1/brain?user_id=...`` and return the bound user."""
        if not isinstance(path, str):
            raise WebSocketTransportError("WebSocket path must be text")
        if len(path) > MAX_PATH_CHARS:
            raise WebSocketTransportError("WebSocket path is too long")
        try:
            parsed = urlsplit(path)
        except ValueError as exc:
            raise WebSocketTransportError("WebSocket path is invalid") from exc
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise WebSocketTransportError("WebSocket path must be origin-relative")
        if parsed.path != API_PATH:
            raise WebSocketTransportError(f"WebSocket path must be {API_PATH}")
        try:
            query = parse_qs(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=MAX_QUERY_FIELDS,
            )
        except ValueError as exc:
            raise WebSocketTransportError("WebSocket query is invalid") from exc
        unsupported = sorted(set(query) - {"user_id"})
        if unsupported:
            raise WebSocketTransportError(
                "unsupported WebSocket query parameter: " + unsupported[0]
            )
        values = query.get("user_id", [])
        if len(values) != 1:
            raise WebSocketTransportError(
                "WebSocket connection requires exactly one user_id"
            )
        user_id = values[0]
        if not _valid_user_id(user_id):
            raise WebSocketTransportError("WebSocket user_id is invalid")
        return user_id

    @staticmethod
    def _request_user_ids(message: Mapping[str, Any]) -> tuple[Any, ...]:
        params = message.get("params")
        if not isinstance(params, dict):
            return ()
        candidates: list[Any] = []
        if "user_id" in params:
            candidates.append(params.get("user_id"))
        method = message.get("method")
        if not isinstance(method, str):
            return tuple(candidates)
        nested_key = {
            "ingest": "event",
            "record_feedback": "feedback",
            "build_context": "context",
            "analyze_developer": "context",
            "reason": "context",
        }.get(method)
        if nested_key is not None:
            nested = params.get(nested_key)
            if isinstance(nested, dict) and "user_id" in nested:
                candidates.append(nested.get("user_id"))
        return tuple(candidates)

    def _identity_error(
        self,
        message: Mapping[str, Any],
        connection_user_id: str,
    ) -> ApiResponse[Any] | None:
        for candidate in self._request_user_ids(message):
            if isinstance(candidate, str) and candidate != connection_user_id:
                raw_method = message.get("method")
                method = None
                if isinstance(raw_method, str):
                    try:
                        method = ApiMethod(raw_method)
                    except ValueError:
                        method = None
                return error_response(
                    _bounded_request_id(message.get("id")),
                    method,
                    ApiError(
                        code=ApiErrorCode.BAD_REQUEST,
                        message=(
                            "request user_id does not match connection user_id"
                        ),
                        source="websocket",
                    ),
                )
        return None

    def protocol_error(
        self,
        message: str,
        *,
        request_id: str = "",
    ) -> ApiResponse[Any]:
        return error_response(
            request_id,
            None,
            ApiError(
                code=ApiErrorCode.BAD_REQUEST,
                message=message,
                source="websocket",
            ),
        )

    def handle_message(
        self,
        raw: str | bytes | bytearray | memoryview,
        connection_user_id: str,
    ) -> ApiResponse[Any]:
        """Decode one socket message and route it through ``BrainApi.handle``."""
        if not _valid_user_id(connection_user_id):
            raise ValueError("connection_user_id must be a valid user identity")
        if isinstance(raw, str):
            try:
                raw_bytes = raw.encode("utf-8")
            except UnicodeEncodeError:
                return self.protocol_error("WebSocket text is not valid Unicode")
            text = raw
        elif isinstance(raw, (bytes, bytearray, memoryview)):
            raw_bytes = bytes(raw)
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                return self.protocol_error(
                    f"invalid UTF-8 message: {exc.reason}",
                )
        else:
            return self.protocol_error("WebSocket message must be text or bytes")
        if len(raw_bytes) > self._max_message_bytes:
            return self.protocol_error(
                f"WebSocket message exceeds {self._max_message_bytes} bytes"
            )
        try:
            message = json.loads(
                text,
                parse_constant=_reject_json_constant,
                parse_float=_parse_json_float,
            )
        except json.JSONDecodeError as exc:
            return self.protocol_error(f"invalid JSON: {exc.msg}")
        except (RecursionError, ValueError) as exc:
            return self.protocol_error(f"invalid JSON: {exc}")
        if not isinstance(message, dict):
            return self.protocol_error(
                "request must be a JSON object envelope"
            )
        try:
            _validate_unicode(message)
        except ValueError as exc:
            return self.protocol_error(f"invalid JSON: {exc}")
        identity_error = self._identity_error(message, connection_user_id)
        if identity_error is not None:
            return identity_error
        try:
            return self._api.handle(message)
        except Exception as exc:
            return error_response(
                _bounded_request_id(message.get("id")),
                None,
                ApiError(
                    code=ApiErrorCode.INTERNAL_ERROR,
                    message="internal failure",
                    details={"exception": type(exc).__name__},
                    source="websocket",
                ),
            )


class WebSocketEventSink:
    """Synchronous ``EventSink`` with a bounded per-connection event buffer."""

    def __init__(
        self,
        event_capacity: int = DEFAULT_EVENT_QUEUE_SIZE,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        if isinstance(event_capacity, bool) or event_capacity < 1:
            raise ValueError("event_capacity must be a positive integer")
        self._loop = loop or asyncio.get_running_loop()
        self._event_capacity = event_capacity
        self._items: deque[_OutboundFrame] = deque()
        self._buffered_events = 0
        self._unfinished = 0
        self._item_waiter: asyncio.Future[None] | None = None
        self._drain_waiter: asyncio.Future[None] | None = None
        self._response_waiter: asyncio.Future[None] | None = None
        self._response_pending = False
        self._state_lock = threading.Lock()
        self._closed = False
        self._accepted = 0
        self._dropped = 0

    @property
    def event_capacity(self) -> int:
        return self._event_capacity

    @property
    def accepted(self) -> int:
        with self._state_lock:
            return self._accepted

    @property
    def dropped(self) -> int:
        with self._state_lock:
            return self._dropped

    @property
    def queued(self) -> int:
        with self._state_lock:
            return len(self._items)

    @property
    def closed(self) -> bool:
        with self._state_lock:
            return self._closed

    @staticmethod
    def _resolve(future: asyncio.Future[None] | None) -> None:
        if future is not None and not future.done():
            future.set_result(None)

    def _wake(
        self,
        future: asyncio.Future[None] | None,
    ) -> None:
        if future is None or future.done() or self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._resolve, future)
        except RuntimeError:
            pass

    def emit(self, event: BrainEvent) -> None:
        if not isinstance(event, BrainEvent):
            raise TypeError("EventSink.emit expects a BrainEvent contract")
        if self._loop.is_closed():
            with self._state_lock:
                self._dropped += 1
            return
        frame = _OutboundFrame(_wire_text(event_frame(event)), True)
        with self._state_lock:
            if self._closed or self._buffered_events >= self._event_capacity:
                self._dropped += 1
                return
            self._items.append(frame)
            self._buffered_events += 1
            self._unfinished += 1
            self._accepted += 1
            waiter = self._item_waiter
        self._wake(waiter)

    def enqueue_response(
        self,
        response: ApiResponse[Any],
    ) -> asyncio.Future[None] | None:
        if self._loop.is_closed():
            return None
        frame = _OutboundFrame(_wire_text(response_frame(response)), False)
        with self._state_lock:
            if self._closed or self._response_pending:
                return None
            delivery = self._loop.create_future()
            self._items.append(frame)
            self._unfinished += 1
            self._response_waiter = delivery
            self._response_pending = True
            waiter = self._item_waiter
        self._wake(waiter)
        return delivery

    async def _next_frame(self) -> _OutboundFrame | None:
        while True:
            with self._state_lock:
                if self._items:
                    return self._items.popleft()
                if self._closed:
                    return None
                waiter = self._loop.create_future()
                self._item_waiter = waiter
            try:
                await waiter
            finally:
                with self._state_lock:
                    if self._item_waiter is waiter:
                        self._item_waiter = None

    def _frame_sent(self, frame: _OutboundFrame) -> None:
        response_waiter = None
        with self._state_lock:
            if frame.is_event:
                self._buffered_events = max(0, self._buffered_events - 1)
            else:
                self._response_pending = False
                response_waiter = self._response_waiter
                self._response_waiter = None
            self._unfinished = max(0, self._unfinished - 1)
            drain_waiter = self._drain_waiter if self._unfinished == 0 else None
        self._resolve(response_waiter)
        self._resolve(drain_waiter)

    async def wait_until_flushed(self) -> None:
        while True:
            with self._state_lock:
                if self._unfinished == 0:
                    return
                waiter = self._loop.create_future()
                self._drain_waiter = waiter
            try:
                await waiter
            finally:
                with self._state_lock:
                    if self._drain_waiter is waiter:
                        self._drain_waiter = None

    async def write_to(self, connection: WebSocketSendConnection) -> None:
        while True:
            frame = await self._next_frame()
            if frame is None:
                return
            try:
                await connection.send(frame.text)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.close()
                raise
            finally:
                self._frame_sent(frame)

    def close(self) -> None:
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            while self._items:
                frame = self._items.popleft()
                self._unfinished = max(0, self._unfinished - 1)
                if frame.is_event:
                    self._buffered_events = max(0, self._buffered_events - 1)
                    self._dropped += 1
            item_waiter = self._item_waiter
            response_waiter = self._response_waiter
            self._response_waiter = None
            self._response_pending = False
            drain_waiter = (
                self._drain_waiter if self._unfinished == 0 else None
            )
        self._resolve(item_waiter)
        self._resolve(response_waiter)
        self._resolve(drain_waiter)


class WebSocketEventRouter:
    """Route synchronous Brain events to sockets bound to the same user."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocketEventSink]] = {}
        self._users_by_sink: dict[WebSocketEventSink, str] = {}
        self._lock = threading.RLock()
        self._emitted = 0

    @property
    def emitted(self) -> int:
        return self._emitted

    @property
    def connection_count(self) -> int:
        with self._lock:
            return len(self._users_by_sink)

    def connections_for_user(self, user_id: str) -> int:
        if not _valid_user_id(user_id):
            return 0
        with self._lock:
            return len(self._connections.get(user_id, ()))

    def register(self, user_id: str, sink: WebSocketEventSink) -> None:
        if not _valid_user_id(user_id):
            raise ValueError("user_id must be a valid user identity")
        if not isinstance(sink, WebSocketEventSink):
            raise TypeError("sink must be a WebSocketEventSink")
        with self._lock:
            if sink in self._users_by_sink:
                raise ValueError("WebSocket sink is already registered")
            self._connections.setdefault(user_id, set()).add(sink)
            self._users_by_sink[sink] = user_id

    def unregister(self, user_id: str, sink: WebSocketEventSink) -> None:
        with self._lock:
            if self._users_by_sink.get(sink) != user_id:
                return
            self._users_by_sink.pop(sink, None)
            connections = self._connections.get(user_id)
            if connections is None:
                return
            connections.discard(sink)
            if not connections:
                self._connections.pop(user_id, None)

    def emit(self, event: BrainEvent) -> None:
        if not isinstance(event, BrainEvent):
            raise TypeError("EventSink.emit expects a BrainEvent contract")
        with self._lock:
            self._emitted += 1
            sinks = tuple(self._connections.get(event.user_id, ()))
            for sink in sinks:
                sink.emit(event)


def _load_websockets_serve() -> Callable[..., Awaitable[Any]]:
    try:
        module = importlib.import_module("websockets")
    except ImportError as exc:
        raise RuntimeError(
            "WebSocket server dependency is unavailable; install project dependencies"
        ) from exc
    serve = getattr(module, "serve", None)
    if not callable(serve):
        raise RuntimeError("installed websockets package does not expose serve()")
    return serve


class WebSocketBrainServer:
    """Async WebSocket server over one shared, serialized Brain API service."""

    def __init__(
        self,
        api: BrainApi,
        router: WebSocketEventRouter,
        *,
        event_queue_size: int = DEFAULT_EVENT_QUEUE_SIZE,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
        origins: Sequence[str | None] = (None,),
        allow_non_loopback: bool = False,
    ) -> None:
        if not isinstance(api, BrainApi):
            raise TypeError("WebSocketBrainServer requires a BrainApi")
        if not isinstance(router, WebSocketEventRouter):
            raise TypeError("WebSocketBrainServer requires a WebSocketEventRouter")
        if api.service.sink is not router:
            raise ValueError("BrainService sink must be this WebSocketEventRouter")
        if isinstance(event_queue_size, bool) or event_queue_size < 1:
            raise ValueError("event_queue_size must be a positive integer")
        if isinstance(max_message_bytes, bool) or max_message_bytes < 1:
            raise ValueError("max_message_bytes must be a positive integer")
        if isinstance(origins, (str, bytes)) or not isinstance(origins, Sequence):
            raise TypeError("origins must be a sequence of origin strings or None")
        if any(
            origin is not None and not isinstance(origin, str)
            for origin in origins
        ):
            raise TypeError("origins entries must be origin strings or None")
        self._api = api
        self._router = router
        self._transport = WebSocketBrainTransport(
            api,
            max_message_bytes=max_message_bytes,
        )
        self._event_queue_size = event_queue_size
        self._max_message_bytes = max_message_bytes
        self._origins = tuple(origins)
        self._allow_non_loopback = allow_non_loopback
        self._request_lock = asyncio.Lock()
        self._server: Any = None
        self._stop_event: asyncio.Event | None = None
        self._stop_requested = False

    @property
    def api(self) -> BrainApi:
        return self._api

    @property
    def router(self) -> WebSocketEventRouter:
        return self._router

    @property
    def origins(self) -> tuple[str | None, ...]:
        return self._origins

    @property
    def server(self) -> Any:
        return self._server

    @staticmethod
    async def _close_connection(
        connection: Any,
        *,
        code: int,
        reason: str,
    ) -> None:
        encoded = reason.encode("utf-8")[:_MAX_CLOSE_REASON_BYTES]
        await connection.close(
            code=code,
            reason=encoded.decode("utf-8", errors="ignore"),
        )

    async def _run_request(
        self,
        raw: str | bytes,
        user_id: str,
    ) -> ApiResponse[Any]:
        async with self._request_lock:
            worker = asyncio.create_task(
                asyncio.to_thread(
                    self._transport.handle_message,
                    raw,
                    user_id,
                ),
                name="digital-brain-websocket-request",
            )
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                await asyncio.gather(worker, return_exceptions=True)
                raise

    async def _receive_messages(
        self,
        connection: Any,
        sink: WebSocketEventSink,
        user_id: str,
    ) -> None:
        async for raw in connection:
            if sink.closed:
                return
            response = await self._run_request(raw, user_id)
            delivery = sink.enqueue_response(response)
            if delivery is None:
                return
            await delivery
            if sink.closed:
                return

    async def handle_connection(self, connection: Any) -> None:
        try:
            user_id = self._transport.user_id_from_path(_connection_path(connection))
        except WebSocketTransportError as exc:
            await self._close_connection(
                connection,
                code=1008,
                reason=str(exc),
            )
            return
        sink = WebSocketEventSink(self._event_queue_size)
        self._router.register(user_id, sink)
        writer = asyncio.create_task(
            sink.write_to(connection),
            name="digital-brain-websocket-writer",
        )
        receiver = asyncio.create_task(
            self._receive_messages(connection, sink, user_id),
            name="digital-brain-websocket-receiver",
        )
        try:
            done, _pending = await asyncio.wait(
                {receiver, writer},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if writer in done and not writer.cancelled():
                writer.exception()
                try:
                    await self._close_connection(
                        connection,
                        code=1011,
                        reason="event writer failed",
                    )
                except Exception:
                    pass
        finally:
            receiver.cancel()
            writer.cancel()
            await asyncio.gather(receiver, writer, return_exceptions=True)
            self._router.unregister(user_id, sink)
            sink.close()

    def stop(self) -> None:
        self._stop_requested = True
        if self._stop_event is not None:
            self._stop_event.set()

    async def serve_forever(self, host: str, port: int) -> None:
        if not _is_loopback_host(host) and not self._allow_non_loopback:
            raise ValueError(
                "non-loopback WebSocket binding requires "
                "allow_non_loopback=True"
            )
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("port must be an integer between 0 and 65535")
        if self._stop_requested:
            return
        serve = _load_websockets_serve()
        stop_event = asyncio.Event()
        self._stop_event = stop_event
        try:
            async with serve(
                self.handle_connection,
                host,
                port,
                origins=self._origins,
                max_size=self._max_message_bytes,
                max_queue=DEFAULT_LIBRARY_QUEUE_SIZE,
            ) as server:
                self._server = server
                stop_task = asyncio.create_task(
                    stop_event.wait(),
                    name="digital-brain-websocket-stop",
                )
                close_task = asyncio.create_task(
                    server.wait_closed(),
                    name="digital-brain-websocket-closed",
                )
                try:
                    await asyncio.wait(
                        {stop_task, close_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    stop_task.cancel()
                    close_task.cancel()
                    await asyncio.gather(
                        stop_task,
                        close_task,
                        return_exceptions=True,
                    )
                    self._server = None
        finally:
            self._stop_event = None


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m core.transport.websocket``."""
    parser = argparse.ArgumentParser(
        prog="digital-brain-websocket",
        description=(
            "Digital Brain WebSocket transport. Connects to "
            "/v1/brain?user_id=... and exchanges the stdio response/event "
            "frame envelope over a bounded, user-isolated socket."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default="data/brain.sqlite3")
    parser.add_argument(
        "--event-queue-size",
        type=int,
        default=DEFAULT_EVENT_QUEUE_SIZE,
    )
    parser.add_argument(
        "--max-message-bytes",
        type=int,
        default=MAX_MESSAGE_BYTES,
    )
    parser.add_argument(
        "--provider",
        default=None,
        help=(
            "LLM provider for understanding/analysis. Defaults to "
            "BRAIN_LLM_PROVIDER, then 'heuristic'."
        ),
    )
    parser.add_argument(
        "--origin",
        action="append",
        help=(
            "Allowed browser Origin. Repeat for multiple origins. If omitted, "
            "only clients without an Origin header are accepted."
        ),
    )
    parser.add_argument(
        "--allow-unauthenticated-non-loopback",
        action="store_true",
        help=(
            "Allow a non-loopback bind without authentication. This is unsafe "
            "for an untrusted network."
        ),
    )
    args = parser.parse_args(argv)
    if not args.allow_unauthenticated_non_loopback and not _is_loopback_host(
        args.host
    ):
        parser.error(
            "non-loopback binding requires "
            "--allow-unauthenticated-non-loopback"
        )

    router = WebSocketEventRouter()
    provider = resolve_llm_provider(args.provider)
    service = build_brain_service(args.db, sink=router, provider=provider)
    try:
        server = WebSocketBrainServer(
            BrainApi(service),
            router,
            event_queue_size=args.event_queue_size,
            max_message_bytes=args.max_message_bytes,
            origins=tuple(args.origin) if args.origin else (None,),
            allow_non_loopback=args.allow_unauthenticated_non_loopback,
        )
        print(
            f"digital-brain-websocket listening on ws://{args.host}:{args.port}"
            f"{API_PATH}?user_id=<id>",
            file=sys.stderr,
            flush=True,
        )
        asyncio.run(server.serve_forever(args.host, args.port))
    except KeyboardInterrupt:
        pass
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
