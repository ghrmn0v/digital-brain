# WebSocket Transport Adapter (Phase 8, Slice 4C)

`core/transport/websocket.py` exposes the existing Brain API and Brain events over
one bidirectional WebSocket connection. It is a transport adapter only:

```text
WebSocket message
  -> core/transport/websocket.py   (decode, identity guard, framing)
  -> BrainApi.handle()             (single request-processing entry point)
  -> BrainService
  -> Core Brain

BrainService
  -> WebSocketEventRouter          (user-bound EventSink fan-out)
  -> one bounded sink per connection
  -> WebSocket event frame
```

The Core modules do not import `asyncio`, `websockets`, sockets, HTTP, or this
adapter. The Brain still proposes actions; this transport never executes one.

## Connection endpoint

Connect to:

```text
ws://127.0.0.1:8766/v1/brain?user_id=<url-encoded-user-id>
```

The connection path is exactly `/v1/brain`. Admission requires exactly one
`user_id` query field. The identity must be 1–512 characters, must not have
leading/trailing whitespace, control characters or Unicode surrogate code points.
Unknown query fields, duplicate identities, blank identities, paths longer than
2,048 characters and more than four parsed query fields are rejected before the
connection is registered.

A bad path or identity closes the socket with WebSocket status `1008` and a
bounded reason. It does not create a service request.

## Identity and authorization boundary

The query `user_id` binds one socket to one owner for routing and request
isolation. It is **not authentication**: a native client that can reach the
server can choose the value.

For every v1 request shape that carries ownership, the adapter checks the
matching `user_id` before calling `BrainApi.handle()`:

- top-level `params.user_id` methods, including user reads and preferences;
- `ingest.params.event.user_id`;
- `record_feedback.params.feedback.user_id`;
- `build_context`, `analyze_developer` and `reason`
  `params.context.user_id`;
- `understand.params.user_id` when supplied.

A string ownership value that differs from the connection identity receives a
canonical `bad_request` response. Malformed ownership values continue through
`BrainApi` and receive its normal typed validation error. Read-only `ping` and
`describe` do not require an ownership field after the connection identity has
already been established.

The server fails closed for non-loopback binds. Programmatic use must set
`allow_non_loopback=True`, and the CLI requires
`--allow-unauthenticated-non-loopback`. Both are explicit unsafe opt-ins for an
untrusted network; real deployment still needs authentication and TLS.

## Request format

Each WebSocket message is one complete `ApiRequest` JSON object, matching the
versioned contract exactly:

```json
{"id":"req-1","method":"ingest","version":"v1","params":{"event":{}}}
```

Both WebSocket text messages and UTF-8 binary messages are accepted. Blank,
malformed, non-object, non-standard-constant, non-finite-number, unpaired
surrogate, recursively excessive, oversized and invalid-envelope inputs all
remain inside the typed `ApiResponse` boundary where possible; they do not
crash the connection.

The transport and the `websockets` server both enforce
`MAX_MESSAGE_BYTES = 1_000_000`. The library receive queue is also explicitly
bounded to 32 messages. Requests are processed sequentially per connection,
and all connections share one serialized `BrainApi`/SQLite service lock.

## Response and event frames

One socket carries two frame types, reusing the stdio envelope:

| frame | wire shape |
|---|---|
| response | `{"kind":"response","payload":<ApiResponse>}` |
| event | `{"kind":"event","payload":<BrainEvent>}` |

Frames are deterministic compact JSON with recursively sorted keys and no
trailing newline. WebSocket serialization uses ASCII-safe escaping so every
outbound frame is valid UTF-8 even when application text contains non-ASCII
characters.

Every request receives exactly one response frame. Existing `ApiErrorCode`
values are unchanged:

| code | WebSocket behavior |
|---|---|
| `bad_request` | response frame; connection remains open |
| `unknown_method` | response frame; connection remains open |
| `version_unsupported` | response frame; connection remains open |
| `validation_error` | response frame; connection remains open |
| `not_configured` | response frame; connection remains open |
| `internal_error` | response frame; only exception class name in details |

Malformed JSON cannot reliably recover a request id and therefore uses `""`.
A decoded object with an id preserves its bounded request id.

## Event routing and ordering

`WebSocketEventRouter` is the service-owned `EventSink`. A `BrainEvent` is sent
only to sockets registered for the exact `event.user_id`; payload contents
never decide routing. Multiple sockets for the same user receive the same event
object and therefore the same `BrainEvent.id`.

Events emitted synchronously by one request are appended before that request's
response. One response is allowed to be outstanding per connection, and the
next request is not processed until that response has been handed to the socket
writer. This preserves the stdio per-operation ordering without making the
shared service concurrent.

`analyze_developer` returns its event list in the response and also emits the
same events through the sink. A bidirectional client can see both
representations and must deduplicate by `BrainEvent.id`; the transport does not
redispatch result events.

## Bounded buffering and delivery semantics

Each connection has a bounded event buffer, default 128 frames:

- event frames use **drop-newest** overflow: once 128 events are buffered, a new
  event is dropped and counted;
- one response frame is reserved outside that event limit and is never silently
  evicted;
- the writer preserves FIFO order across accepted event and response frames;
- a slow client applies backpressure to its next request but does not block the
  asyncio event loop;
- disconnect or writer failure discards queued frames and unregisters the sink.

These are transport-local buffers. They do not change the Core event-delivery
contract: delivery remains in-process, at-most-once and best-effort. There is
no persistence, retry, replay, acknowledgement, delivery ledger or broker.
Clients deduplicate by event id and never assume replay after reconnect.

A slow client can cause events to be dropped, but its response remains
prioritized over accepting another request. This prevents unbounded outbound
response buffering.

## Concurrency and lifecycle

`BrainApi.handle()` and the shared SQLite-backed `BrainService` are synchronous.
Each request runs through `asyncio.to_thread`, while one server-wide async lock
serializes access. Handler cancellation waits for its already-running worker
before releasing that lock, so a late thread cannot mutate SQLite concurrently
with another connection.

This deliberate single-worker design has one prototype limitation: an operation
that never returns, such as an unbounded custom provider or database call, can
block other clients and graceful shutdown. Built-in provider timeouts and
database operations remain the responsibility of their existing boundaries; the
WebSocket transport does not fake cancellation of a running thread.

The receive and writer tasks are monitored together. A writer failure closes
the connection with status `1011`, cancels the receiver and unregisters the
event sink. `Ctrl-C`, `WebSocketBrainServer.stop()` or closing the underlying
websockets server shuts down the loopback listener; CLI shutdown then closes the
`BrainService`.

## Browser Origin policy

The default allowed-origin list is `[None]`: clients without an `Origin` header
(such as native clients) are accepted, while browser requests are rejected.
Repeat `--origin` to allow explicit browser origins:

```bash
python -m core.transport.websocket --origin https://app.example.test
```

Supplying browser origins does not add authentication. Keep authorization and
TLS at the deployment boundary.

## CLI

```bash
python -m core.transport.websocket \
  --host 127.0.0.1 \
  --port 8766 \
  --db data/brain.sqlite3
```

Flags:

- `--host` — default `127.0.0.1`; non-loopback values require the explicit
  unauthenticated opt-in;
- `--port` — default `8766`, `0` is useful for an ephemeral programmatic bind;
- `--db` — default `data/brain.sqlite3`, `:memory:` is supported;
- `--event-queue-size` — per-connection event capacity, default `128`;
- `--max-message-bytes` — incoming message limit, default `1_000_000`;
- `--origin` — allowed browser origin; repeat for multiple values;
- `--allow-unauthenticated-non-loopback` — explicit unsafe bind opt-in.

The project declares `websockets>=12`. The transport module itself imports that
package lazily, so importing `core`, testing the protocol adapter, or using
stdio/HTTP does not import or instantiate the WebSocket server dependency.

## Test coverage

`tests/test_websocket_transport.py` uses injected fake connections and covers:

- path, query, identity, message-size and strict-JSON admission;
- text/binary requests and every existing typed error path;
- nested ownership checks and internal-error redaction;
- event routing, user isolation, deterministic frames and overflow;
- one outstanding response, writer failure and cancellation safety;
- shared-service serialization, loopback enforcement and graceful stop;
- lazy dependency loading and Core/transport architecture boundaries.
