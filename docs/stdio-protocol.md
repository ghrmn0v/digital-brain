# Stdio JSON-lines protocol (Phase 8 Slice 3 — Part B: the daemon)

The **stdio JSON-lines daemon** (`core/transport/stdio.py`, run as
`python -m core.transport`) is the first concrete transport for the typed
Brain API from Part A. It is strictly **transport-only**: it never changes the
`ApiRequest`/`ApiResponse`/`BrainEvent` contracts, never touches the internal
modules and never executes anything — it only adapts two existing entry
points:

- `BrainApi.handle(message)` — the single request-processing entry point;
- the `EventSink` port — where the Brain streams every state-transition event.

```text
stdin (one JSON line per request)         stdout (one JSON line per frame)
┌─────────────────────────────────┐  ┌──────────────────────────────────┐
│ {"id":"r1","method":"ingest",…} │→ │ {"kind":"event",  "payload":{…}} │
│ {"id":"r1","method":"ingest",…} │→ │ {"kind":"event",  "payload":{…}} │
│ {"id":"r2","method":"ping",…}   │→ │ {"kind":"response","payload":{…}} │
│            …EOF…                │  │ {"kind":"response","payload":{…}} │
└─────────────────────────────────┘  └──────────────────────────────────┘
```

## Why a frame envelope?

`ApiResponse` has no top-level discriminator field, and `BrainEvent` lines are
generated as side effects of a request. Both travel on the **same stdout
stream**, so each line is wrapped in a minimal, unambiguous envelope whose
`kind` field tells the consumer what it is:

| frame | wire shape |
|---|---|
| response | `{"kind": "response", "payload": <ApiResponse>}` |
| event | `{"kind": "event", "payload": <BrainEvent>}` |

`payload` is the `model_dump(mode="json")` of the contract object — nothing is
invented, re-ordered semantically or stripped.

## Request format (stdin)

One `ApiRequest` per line, verbatim JSON (JSON Lines):

```json
{"id":"req_1","method":"ingest","params":{"event":{...},"correlation_id":"corr_1"}}
```

- `id`, `method`, `version`, `params` follow the Part A contract exactly; the
  daemon does not inspect them — `BrainApi.handle` validates. Correlation belongs
  inside the method's `params` model, not at the request top level.
- Blank / whitespace-only lines are ignored (no response is written for them).
- Everything else — including a non-object JSON (`[1,2,3]`) — is a malformed
  request and gets a structured error response (see below), never a raise.
- After EOF on stdin the daemon flushes stdout, closes the attached
  `BrainService` and exits cleanly.

## Response format (stdout)

Exactly **one line per request**, in order:

```json
{"kind":"response","payload":{"id":"req_1","method":"ingest","version":"v1","ok":true,
 "result":{"outcome":"accepted","event_id":"evt_cli","user_id":"usr_cli","correlation_id":"corr_cli",
            "memory_ids":["mem_..."],"events_emitted":1,"duplicate_of_event_id":null,"reason":null},
 "error":null}}
```

On failure `ok` is `false` and `error` carries the typed `ApiError`
(`code`, `message`, `source`, `details`):

```json
{"kind":"response","payload":{"id":"r2","method":"ping","version":"v1","ok":false,
 "error":{"code":"version_unsupported","message":"unsupported contract version: 'v2'",
           "source":"BrainApi","details":{}},"result":null}}
```

## Event format (stdout)

Every `BrainEvent` the service emits **while a request runs** is written as
one frame, before the response of that request:

```json
{"kind":"event","payload":{"id":"evt_…","type":"memory.created","version":"v1",
 "timestamp":"2026-09-25T08:22:12Z","user_id":"usr_cli","source":{...},
 "related_ids":["mem_…"],"payload":{"memory_id":"mem_…","correlation_id":"corr_cli",...}}}
```

Ownership and causality are preserved in the payload: `user_id`, the event
`type`, and the `correlation_id` (when supplied) travel untouched. Events do
**not** carry the request `id` — they are side effects, not answers; a client
correlates them to a request through `correlation_id`.

## Error behaviour (regression-tested)

- Malformed JSON → `bad_request` (`"invalid JSON: …"`), request `id` is `""`.
- Non-object JSON → `bad_request` (`"expected a JSON object envelope"`).
- Invalid `ApiRequest` (e.g. non-string `id`) → existing `bad_request` path of
  `BrainApi.handle`.
- Unknown method / unsupported version / invalid params →
  `unknown_method` / `version_unsupported` / `validation_error` (unchanged
  Part A mapping).
- Any unexpected exception inside the handler → `internal_error` with
  **only** the exception class name in `error.details` — never the message,
  never a traceback, never the class of the underlying failure.
- **One bad line never terminates the daemon** — processing continues with the
  next line.

## Lifecycle

1. Start: `python -m core.transport [--db PATH]` (default DB
   `data/brain.sqlite3`, `:memory:` supported). Events go to stdout through a
   `JsonLinesEventSink`; human diagnostics go to stderr.
2. Run: synchronous single-threaded loop — read line → `handle` → (events) →
   response.
3. Shutdown: stdin EOF → flush → `service.close()` → a one-line summary on
   stderr (`shutdown: <n> request(s), <m> event(s) written`) → exit `0`.

## Determinism

Every frame is serialized by one deterministic helper: recursive key sorting
(`sort_keys=True`), minimal separators (`,`/`:`), `ensure_ascii=False`.
Identical requests produce byte-identical responses, so clients can diff or
cache frames safely.

## Platform independence

The daemon touches only stdlib text streams (`sys.stdin` / `sys.stdout` /
`sys.stderr`) and the injected streams — no sockets, no HTTP/WebSocket, no
terminal/OS/device-specific calls, no subprocesses. It is therefore usable
from any wrapper (classic shell pipes, `subprocess.Popen`, systemd, a
custom CLI) on any OS. HTTP and WebSocket are separate completed transports over
the same `BrainApi.handle` surface; mobile clients consume those protocols or
the published schema without adding device code to Core.

## Testability (no subprocess needed)

`StdioDaemon` and `JsonLinesEventSink` are dependency-injected
(`api`, `stdin`, `stdout`, `sink`, `serializer`, `diagnostics`), so the whole
protocol is exercised in-process with `io.StringIO` streams
(`tests/test_stdio_daemon.py`).