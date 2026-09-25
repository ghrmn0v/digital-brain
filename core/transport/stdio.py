"""Stdio JSON-lines transport daemon (Phase 8, Slice 3 Part B).

A synchronous, transport-only adapter that serves a :class:`BrainApi` over
JSON Lines. It reads exactly one JSON object per stdin line, routes it through
:meth:`BrainApi.handle` — the single request-processing entry point created in
Slice 3 Part A — and writes exactly one JSON object per stdout line for every
result and for every Brain event the service emits while a request runs.

Wire protocol (documented in ``docs/stdio-protocol.md``) is an unambiguous
frame envelope, since :class:`ApiResponse` carries no discriminator field:

    // one request per stdin line — exactly the ApiRequest contract:
    {"id": "req-1", "method": "ingest", "params": {...}, ...}

    // exactly one line per response:
    {"kind": "response", "payload": { ...ApiResponse... }}

    // one line per BrainEvent emitted while a request runs:
    {"kind": "event", "payload": { ...BrainEvent... }}

Guarantees written here (and enforced by tests):

- ``BrainApi.handle`` stays the single entry point; this module only adapts.
- One bad line (malformed JSON, non-object JSON, invalid ApiRequest, unknown
  method, bad version, invalid params) yields a structured ``ApiResponse``
  error and never terminates the daemon.
- Internal exceptions never leak message text or tracebacks — the response
  carries only the exception type name under ``error.details``.
- EOF on stdin is the clean-shutdown signal: streams are flushed and the
  attached :class:`BrainService` is closed.
- stdout carries protocol frames only; diagnostics go to a separate stream.
- No sockets, no HTTP/WebSocket, no terminal/OS/device assumptions, no
  subprocesses — just stdlib text streams, hence platform-independent.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Mapping, Sequence, TextIO

from contracts.api import (
    ApiError,
    ApiErrorCode,
    ApiResponse,
    EventEnvelope,
    ResponseEnvelope,
    error_response,
    event_frame,
    response_frame,
)
from contracts.brain_events.events import BrainEvent

from core.brain_events.sink import EventSink, NullEventSink
from core.service.api import BrainApi
from core.service.brain_service import BrainService, build_brain_service


def default_json_line(payload: Mapping[str, Any]) -> str:
    """Serialize one wire frame deterministically and compactly.

    Keys are sorted recursively and separators are minimal, so the same frame
    always serializes to the same bytes regardless of construction order.
    Non-ASCII characters are kept (``ensure_ascii=False``).
    """
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


class JsonLinesEventSink:
    """:class:`EventSink` adapter: one BrainEvent -> one JSON-lines frame.

    A BrainService wired with this sink streams every emitted event to the same
    output stream the daemon uses for responses, one frame per line.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        serializer: Callable[[Mapping[str, Any]], str] = default_json_line,
    ) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._serializer = serializer
        self._count = 0

    def emit(self, event: BrainEvent) -> None:
        if not isinstance(event, BrainEvent):
            raise TypeError("EventSink.emit expects a BrainEvent contract")
        self._stream.write(self._serializer(event_frame(event)))
        self._stream.flush()
        self._count += 1

    @property
    def count(self) -> int:
        """Number of event frames written so far."""
        return self._count


class StdioDaemon:
    """Synchronous JSON-lines daemon over one :class:`BrainApi`.

    Fully dependency-injected (api, stdin, stdout, sink, serializer,
    diagnostics) so every behaviour is exercisable in-process with
    ``io.StringIO`` streams — no real process is required to test it.
    """

    def __init__(
        self,
        api: BrainApi,
        *,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        sink: EventSink | None = None,
        serializer: Callable[[Mapping[str, Any]], str] = default_json_line,
        diagnostics: TextIO | None = None,
    ) -> None:
        if not isinstance(api, BrainApi):
            raise TypeError("StdioDaemon requires a BrainApi")
        self._api = api
        self._stdin = stdin if stdin is not None else sys.stdin
        self._stdout = stdout if stdout is not None else sys.stdout
        self._sink = sink if sink is not None else NullEventSink()
        self._serializer = serializer
        self._diagnostics = diagnostics
        self._request_count = 0

    @property
    def api(self) -> BrainApi:
        return self._api

    @property
    def sink(self) -> EventSink:
        return self._sink

    @property
    def request_count(self) -> int:
        """Number of non-blank requests processed on this daemon."""
        return self._request_count

    def _notice(self, message: str) -> None:
        if self._diagnostics is not None:
            self._diagnostics.write(message + "\n")
            self._diagnostics.flush()

    def _write_response(self, response: ApiResponse[Any]) -> None:
        self._stdout.write(self._serializer(response_frame(response)))
        self._stdout.flush()

    def handle_line(self, raw: str) -> None:
        """Process exactly one input line and write its response frame."""
        text = raw.rstrip("\r\n")
        if not text.strip():
            return
        self._request_count += 1
        try:
            message = json.loads(text)
        except json.JSONDecodeError as exc:
            self._write_response(
                error_response(
                    "",
                    None,
                    ApiError(
                        code=ApiErrorCode.BAD_REQUEST,
                        message=f"invalid JSON: {exc.msg}",
                        source="stdio",
                    ),
                )
            )
            return
        if not isinstance(message, dict):
            self._write_response(
                error_response(
                    "",
                    None,
                    ApiError(
                        code=ApiErrorCode.BAD_REQUEST,
                        message=(
                            "invalid request: expected a JSON object envelope"
                        ),
                        source="stdio",
                    ),
                )
            )
            return
        self._write_response(self._dispatch(message))

    def _dispatch(self, message: Mapping[str, Any]) -> ApiResponse[Any]:
        try:
            return self._api.handle(message)
        except Exception as exc:  # nosec B110 — transport boundary, always typed
            request_id = str(message.get("id") or "").strip()
            return error_response(
                request_id,
                None,
                ApiError(
                    code=ApiErrorCode.INTERNAL_ERROR,
                    message="internal failure",
                    details={"exception": type(exc).__name__},
                    source="stdio",
                ),
            )

    def serve(self) -> None:
        """Read stdin until EOF, framing one response per request.

        EOF is the clean-shutdown signal: stdout is flushed and the attached
        :class:`BrainService` is closed.
        """
        for raw in self._stdin:
            self.handle_line(raw)
        self._stdout.flush()
        self._api.service.close()
        self._notice(
            f"shutdown: {self._request_count} request(s), "
            f"{getattr(self._sink, 'count', 0)} event(s) written"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: ``python -m core.transport.stdio [--db PATH]``."""
    parser = argparse.ArgumentParser(
        prog="digital-brain-stdio",
        description=(
            "Digital Brain stdio JSON-lines daemon. Reads one ApiRequest per "
            "stdin line and writes one JSON frame per stdout line. "
            "Transport-only and platform-independent. EOF shuts down cleanly."
        ),
    )
    parser.add_argument(
        "--db",
        default="data/brain.sqlite3",
        help="SQLite database path (use ':memory:' for a transient brain).",
    )
    args = parser.parse_args(argv)

    sink = JsonLinesEventSink(sys.stdout)
    service = build_brain_service(args.db, sink=sink)
    daemon = StdioDaemon(
        BrainApi(service),
        stdin=sys.stdin,
        stdout=sys.stdout,
        sink=sink,
        diagnostics=sys.stderr,
    )
    daemon.serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())