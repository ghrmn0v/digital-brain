# Client-facing Brain API (Phase 8 Slice 3 — Part A: typed contract)

The **typed, versioned, platform-independent wire contract** clients use to talk
to the Brain. It has two halves:

- `contracts/api/` — the canonical, serializable contract (envelope, method
  registry, typed params, typed results, typed errors). NO implementation logic.
- `core/service/api.py` (`BrainApi`) — the in-process adapter: maps an
  `ApiRequest` to a `BrainService` call and returns a typed `ApiResponse`.

```text
Client (PC / Mobile / Fly / connectors)
   │  ApiRequest (id, method, version, params)
   ▼
BrainApi.handle(message)            ← single transport-facing entry point
   │  validate method + version + envelope
   │  validate typed params
   │  dispatch → BrainService
   ▼
ApiResponse (id, method, version, ok, result | error)
```

## Envelope

`ApiRequest`: `id` (echoed back), `method` (`ApiMethod`), `version` (`"v1"`),
`params` (generic payload — validated per method against its typed model),
optional `source` provenance.

`ApiResponse`: exactly one of `ok=True + result` OR `ok=False + error`
(validated by the model itself).

`ApiError`: fixed additive `code` (`bad_request`, `unknown_method`,
`version_unsupported`, `validation_error`, `not_configured`,
`internal_error`), message, `source`, open `details`.

Every method has a typed `contracts.api.params.*` request model and a typed
`contracts.api.results.*` result model. External-language SDKs generate clients
straight from the JSON Schemas that `describe` returns.

## Methods (v1)

| method | params | result | notes |
|---|---|---|---|
| `ping` | — | `PingResult` | liveness |
| `describe` | — | `DescribeResult` | method list + JSON Schemas |
| `ingest` | `event` (NormalizedSourceEvent), `correlation_id?` | `IngestionResultWire` | deduped + receipted; `memory.created` events |
| `record_feedback` | `feedback` (Feedback), `correlation_id?` | `FeedbackResultWire` | signal + optional `preference.updated` |
| `record_preference` | user_id/name/value/domain… | `PreferenceWire` | `preference.updated` |
| `understand` | `corpus`, `user_id?`, `corpus_id?` | `UnderstandResultWire` | LLM gateway or heuristic fallback |
| `build_context` | DeveloperSnapshotWire, `task?` | `ContextResultWire` | bounded summary, never a dump |
| `analyze_developer` | DeveloperSnapshotWire, `task?`, `ask_deploy?`, `correlation_id?` | `AnalyzeDeveloperResult` | full Loop → plan + events |
| `reason` | DeveloperSnapshotWire, `task?` | `ReasoningWire` | read path, no planning/events |
| `preferences` / `developer_preferences` / `people_summary` | `user_id` | typed read results | user-scoped |
| `learning_status` / `feedback_history` / `personalization_profile` | `user_id` (+`limit?`) | typed read results | user-scoped |

Developer Mode inputs travel as `DeveloperSnapshotWire` — a field-for-field
mirror of the internal `DeveloperContext`; the adapter copies, never infers.

## Guarantees (regression-tested)

- Every exit path is a typed `ApiResponse` — the adapter never leaks a raw
  exception or stack trace (internal failures become `internal_error` with only
  the exception class name in `details`).
- `describe`, `reason`, `learning_status`, preferences reads are deterministic.
- Correlation ids and user ownership are preserved end-to-end; every event in an
  `analyze_developer` result belongs to the requesting user.
- Finding ids are minted fresh per pass (uniqueness), content/counts are
  deterministic across passes.
- `contracts/api` and `core/service/api.py` import NO transport, socket,
  threading, HTTP, WebSocket or async machinery, and `contracts/api` imports no
  `core.*` — both sides stay platform-independent.
- No new event types, no fake ML, nothing is ever executed by the Brain.

## Usage

```python
from core import BrainApi, build_brain_service

api = BrainApi(build_brain_service("data/brain.sqlite3"))

response = api.handle({
    "id": "req_1",
    "method": "ingest",
    "params": {"event": {...}},   # full NormalizedSourceEvent JSON
})
assert response.ok
print(response.result.memory_ids)
```

The **stdio JSON-lines daemon** (Slice 3 Part B, `core.transport`, run as
`python -m core.transport`) is the first concrete transport: it reads exactly
those raw messages line-by-line from stdin, feeds them into
`BrainApi.handle()`, and streams the returned envelope plus every emitted
Brain event back out as JSON-lines frames
(`{"kind":"response"|"event","payload": {...}}`) — see
[`docs/stdio-protocol.md`](stdio-protocol.md). Future transport adapters
(HTTP/WebSocket/IPC) follow the same recipe and nothing in this contract
needs to change.