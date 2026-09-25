"""Minimal HTTP transport adapter for the Brain API (Phase 8, Slice 4A).

A transport-only adapter: an incoming HTTP request is decoded into the same
dict shape every other transport sends to :meth:`BrainApi.handle` — the single
request-processing entry point — and the returned :class:`ApiResponse` is
serialized back as the canonical JSON envelope. No business logic, no
validation, no decision-making lives here.

Dependency direction:

    HTTP request
    -> HTTP transport adapter (this module)
    -> BrainApi.handle()
    -> BrainService
    -> Core Brain

The adapter never touches the database, ``ContextEngine``, ``ReasoningEngine``,
``LearningEngine``, the action planner or event internals directly. Brain
events are produced naturally by the attached :class:`BrainService` through
its own :class:`EventSink`; HTTP does not create a second event system (no
WebSocket/SSE/polling/queues in this slice).

Endpoints:

    POST /v1/brain   one ApiRequest JSON object         -> ApiResponse JSON
    GET  /health     static liveness payload (no user data, no internal state)

HTTP status reflects the deterministic mapping table documented in
``docs/http-transport.md``; the response body always keeps the canonical
``ApiResponse`` structure (id / method / version / ok / result|error).
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from contracts.api import ApiError, ApiErrorCode, ApiResponse, error_response

from core.brain_events.sink import NullEventSink
from core.service.api import BrainApi
from core.service.brain_service import build_brain_service

API_VERSION = "v1"
"""The only contract version this transport serves (matches ``BrainApi``)."""

MAX_BODY_BYTES = 1_000_000
"""Upper bound on a POST body so a single connection cannot exhaust memory."""

HEALTH_PAYLOAD: dict[str, str] = {
    "status": "ok",
    "service": "digital-brain",
    "api_version": API_VERSION,
}
"""Static health payload — deliberately no user data, no internal state."""

# -- HTTP status mapping (deterministic, additive, no new error semantics) ------

_STATUS_BY_CODE: dict[ApiErrorCode, int] = {
    ApiErrorCode.BAD_REQUEST: 400,
    ApiErrorCode.UNKNOWN_METHOD: 404,
    ApiErrorCode.VERSION_UNSUPPORTED: 400,
    ApiErrorCode.VALIDATION_ERROR: 422,
    ApiErrorCode.NOT_CONFIGURED: 503,
    ApiErrorCode.INTERNAL_ERROR: 500,
}
"""Map every existing ``ApiErrorCode`` to exactly one HTTP status."""


def http_status_for(
    response: ApiResponse[Any],
    *,
    table: Mapping[ApiErrorCode, int] | None = None,
) -> int:
    """Return the HTTP status for one :class:`ApiResponse`.

    Success is always ``200``. Every failure maps through the deterministic
    table; an unexpected/missing mapping degrades to ``500`` never to ``200``.
    """
    if not isinstance(response, ApiResponse):
        raise TypeError("http_status_for expects an ApiResponse")
    if response.ok:
        return 200
    code = (
        response.error.code
        if response.error is not None
        else ApiErrorCode.INTERNAL_ERROR
    )
    return (table or _STATUS_BY_CODE).get(code, 500)


def _serialize(payload: Mapping[str, Any]) -> bytes:
    """Deterministic compact JSON (sorted keys, minimal separators, UTF-8)."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class HttpBrainTransport:
    """Transport-only HTTP adapter over one :class:`BrainApi`.

    Fully testable in-process with raw bytes — no sockets required. The
    attached :class:`BrainService` keeps ownership of the event sink; this
    class only converts HTTP bodies into :meth:`BrainApi.handle` calls.
    """

    def __init__(
        self,
        api: BrainApi,
        *,
        status_table: Mapping[ApiErrorCode, int] | None = None,
    ) -> None:
        if not isinstance(api, BrainApi):
            raise TypeError("HttpBrainTransport requires a BrainApi")
        self._api = api
        self._status = dict(status_table or _STATUS_BY_CODE)

    @property
    def api(self) -> BrainApi:
        return self._api

    @property
    def status_table(self) -> dict[ApiErrorCode, int]:
        return dict(self._status)

    def health(self) -> dict[str, str]:
        """Liveness payload — static, no user data, no internal state."""
        return dict(HEALTH_PAYLOAD)

    def protocol_error(
        self,
        message: str,
        *,
        request_id: str = "",
    ) -> tuple[dict[str, Any], int]:
        """Canonical ``bad_request`` ApiResponse for transport-level failures."""
        response = error_response(
            request_id,
            None,
            ApiError(
                code=ApiErrorCode.BAD_REQUEST,
                message=message,
                source="http",
            ),
        )
        return response.model_dump(mode="json"), self.status_code_for(response)

    def status_code_for(self, response: ApiResponse[Any]) -> int:
        return http_status_for(response, table=self._status)

    def handle_body(self, raw: bytes) -> tuple[dict[str, Any], int]:
        """Parse one POST body into a canonical ApiResponse JSON + HTTP status.

        ``BrainApi.handle`` remains the single entry point for requests that
        reach it. Only transport-level decoding (UTF-8/JSON/object shape)
        happens here, mirroring the stdio daemon's line framing.
        """
        try:
            message = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            detail = exc.msg if hasattr(exc, "msg") else str(exc)
            return self.protocol_error(f"invalid JSON body: {detail}")
        if not isinstance(message, dict):
            return self.protocol_error(
                "request body must be a JSON object envelope"
            )
        response = self._api.handle(message)
        return response.model_dump(mode="json"), self.status_code_for(response)


class HttpBrainHandler(BaseHTTPRequestHandler):
    """Routes GET /health and POST /v1/brain to the server's transport."""

    protocol_version = "HTTP/1.1"
    server_version = "DigitalBrainHTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        """Silence per-request access logs (diagnostics stay configurable)."""

    def _transport(self) -> HttpBrainTransport:
        transport = getattr(self.server, "transport", None)
        if not isinstance(transport, HttpBrainTransport):
            raise RuntimeError("server has no HttpBrainTransport attached")
        return transport

    def _reply(self, status: int, payload: Mapping[str, Any]) -> None:
        body = _serialize(payload)
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes | None:
        raw_header = self.headers.get("Content-Length")
        if raw_header is None:
            raw = self.rfile.read(MAX_BODY_BYTES + 1)
        else:
            try:
                length = int(raw_header)
            except ValueError:
                self._reply(
                    *self._transport().protocol_error(
                        "invalid Content-Length"
                    )
                )
                return None
            if length < 0 or length > MAX_BODY_BYTES:
                self._reply(
                    *self._transport().protocol_error(
                        f"request body exceeds {MAX_BODY_BYTES} bytes"
                    )
                )
                return None
            raw = self.rfile.read(length) if length else b""
        if len(raw) > MAX_BODY_BYTES:
            self._reply(
                *self._transport().protocol_error(
                    f"request body exceeds {MAX_BODY_BYTES} bytes"
                )
            )
            return None
        return raw

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/health", "/health/"):
            self._reply(200, self._transport().health())
            return
        self._reply(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/v1/brain", "/v1/brain/"):
            self._reply(404, {"error": "not_found", "path": path})
            return
        raw = self._read_body()
        if raw is None:
            return
        payload, status = self._transport().handle_body(raw)
        self._reply(status, payload)


class HttpBrainServer(HTTPServer):
    """Single-threaded prototype HTTP server serving one HTTP transport."""

    allow_reuse_address = True

    transport: HttpBrainTransport

    def __init__(
        self,
        address: tuple[str, int],
        transport: HttpBrainTransport,
    ) -> None:
        if not isinstance(transport, HttpBrainTransport):
            raise TypeError("HttpBrainServer requires an HttpBrainTransport")
        super().__init__(address, HttpBrainHandler)
        self.transport = transport

    def serve_in_thread(self) -> threading.Thread:
        """Run ``serve_forever`` on a daemon thread (test/lifecycle helper)."""
        thread = threading.Thread(
            target=self.serve_forever,
            name="brain-http",
            daemon=True,
        )
        thread.start()
        return thread


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: ``python -m core.transport.http [--host H] [--port P] [--db PATH]``."""
    parser = argparse.ArgumentParser(
        prog="digital-brain-http",
        description=(
            "Digital Brain minimal HTTP transport. POST /v1/brain (one JSON "
            "ApiRequest) -> canonical ApiResponse JSON; GET /health for "
            "liveness. Transport-only adapter over BrainApi; events flow to "
            "the service's own EventSink (here: NullEventSink, discarded)."
        ),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (default 127.0.0.1 — loopback only).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port to listen on (default 8765).",
    )
    parser.add_argument(
        "--db",
        default="data/brain.sqlite3",
        help="SQLite database path (use ':memory:' for a transient brain).",
    )
    args = parser.parse_args(argv)

    service = build_brain_service(args.db, sink=NullEventSink())
    transport = HttpBrainTransport(BrainApi(service))
    server = HttpBrainServer((args.host, args.port), transport)
    try:
        print(
            f"digital-brain-http listening on http://{args.host}:{args.port} "
            f"(POST /v1/brain, GET /health)",
            file=sys.stderr,
            flush=True,
        )
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())