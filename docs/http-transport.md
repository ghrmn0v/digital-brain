# HTTP Transport Adapter (Phase 8, Slice 4A)

`core/transport/http.py` exposes the existing versioned `ApiRequest` contract
over plain HTTP/JSON using **only the Python standard library**. It is a
*transport* adapter and nothing more: HTTP never talks to the database, the
Context Engine, the Reasoning Engine, the Learning Engine, the action planner
or event internals directly.

```
HTTP request
  -> core/transport/http.py   (transport adapter — decode body, map status)
  -> BrainApi.handle()        (single request-processing entry point)
  -> BrainService
  -> Core Brain
```

## Endpoints

| Method | Path        | Purpose                                             |
| ------ | ----------- | --------------------------------------------------- |
| POST   | `/v1/brain` | One `ApiRequest` JSON object → canonical `ApiResponse` JSON. |
| GET    | `/health`   | Static liveness payload (`{"status":"ok","service":"digital-brain","api_version":"v1"}`). No user data, no internal state. |
| others | any         | `404 {"error":"not_found","path":…}`; unimplemented HTTP methods get the standard `501`. |

## Request format (`POST /v1/brain`)

The body is exactly the transport-independent `ApiRequest` envelope from
`contracts/api`:

```json
{
  "id": "req-1",
  "method": "ingest",
  "version": "v1",
  "params": { "event": { … } }
}
```

`method` is a `contracts/api/methods.py::ApiMethod` value. `params` is a free
dict validated per-method by the same typed `contracts/api/params.py` models
the stdio daemon uses — no duplicated validation exists here.

Bodies are bounded to `MAX_BODY_BYTES` (1,000,000 bytes). A decode failure
(non-UTF-8, malformed JSON, non-object JSON) returns a canonical
`bad_request` `ApiResponse` with HTTP `400`.

## Response format

Every `/v1/brain` response body is `ApiResponse.model_dump(mode="json")` — the
canonical envelope, byte-for-byte the same shape any other transport produces:

```json
{
  "id": "req-1",
  "method": "ingest",
  "version": "v1",
  "ok": true,
  "result": { … },
  "error": null
}
```

On failure `result` is `null` and `error` carries the typed error:

```json
{
  "id": "req-1",
  "method": "ingest",
  "version": "v1",
  "ok": false,
  "result": null,
  "error": { "code": "validation_error", "message": "…", "source": "BrainApi", "details": {} }
}
```

Request `id`, `version`, `correlation_id` and `user_id` are preserved exactly
as `BrainApi`/`BrainService` preserve them. No new business error semantics
were invented — the mapping below only translates the *existing* `ApiErrorCode`
values to HTTP statuses.

## HTTP status mapping

| `ApiErrorCode`            | HTTP status |
| ------------------------- | ----------- |
| (success)                 | `200`       |
| `bad_request`             | `400`       |
| `version_unsupported`     | `400`       |
| `unknown_method`          | `404`       |
| `validation_error`        | `422`       |
| `not_configured`          | `503`       |
| `internal_error`          | `500`       |

The mapping is a single deterministic table (`_STATUS_BY_CODE`) enforced by
`http_status_for()`. An unexpected/missing mapping degrades to `500`, never to
`200`. Clients must branch on `error.code`, not HTTP status alone.

## Event behavior

No second event system is introduced. When a request causes the
`BrainService` to emit `BrainEvent`s, they flow through the service's own
`EventSink` exactly as for any other transport — HTTP just sends the canonical
`ApiResponse` back. The bundled CLI server wires `NullEventSink` (events are
validated and discarded; nothing is accumulated). No WebSockets, SSE, polling,
queues, Redis or Kafka in this slice.

## Relationship to `BrainApi`

`HttpBrainTransport.handle_body(raw)` is the only decoding the adapter does
(UTF-8 → JSON → dict). Everything after that is `BrainApi.handle(message)` —
the same single entry point the stdio daemon uses.

## Security & authentication limitation

**Authentication is deliberately absent at this prototype layer.** The adapter
trusts exactly the same `user_id` ownership information already trusted by
`BrainApi`/`BrainService` and enforces the same user isolation; it does not
invent tokens, sessions or an authZ system. Do not expose this server outside
a trusted loopback/network without adding a real authentication layer. The
`/health` endpoint returns only static fields and never user data or memory
content.

## Local development example

```bash
python -m core.transport.http --db data/brain.sqlite3
# or, with a transient in-memory brain:
python -m core.transport.http --host 127.0.0.1 --port 8765 --db :memory:
```

```bash
curl -s http://127.0.0.1:8765/health
curl -s -X POST http://127.0.0.1:8765/v1/brain \
  -H 'Content-Type: application/json' \
  -d '{"id":"req-1","method":"ping"}'
```

Flags: `--host` (default `127.0.0.1`), `--port` (default `8765`),
`--db` (default `data/brain.sqlite3`). `Ctrl-C` shuts the server down cleanly
(`server_close()` + `service.close()`).