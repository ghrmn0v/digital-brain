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
optional `source` provenance. For event-producing methods, this source is
preserved on the emitted `BrainEvent` envelope; it does not replace the source
or provenance of nested input contracts.

`ApiResponse`: exactly one of `ok=True + result` OR `ok=False + error`
(validated by the model itself).

`ApiError`: fixed additive `code` (`bad_request`, `unknown_method`,
`version_unsupported`, `validation_error`, `not_configured`,
`internal_error`), message, `source`, open `details`.

Every method has a typed `contracts.api.params.*` request model and a typed
`contracts.api.results.*` result model. External-language SDK generators consume
the checked-in `contracts/schemas/brain-api.v1.json` bundle; live clients can
obtain the equivalent per-method schemas from `describe`. Both come from the
public `contracts.api` registry.

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
| `people_timeline` | `user_id`, `person_id`, optional `limit` | `PeopleTimelineResult` | active + historical, source-traceable |
| `learning_status` / `feedback_history` / `personalization_profile` | `user_id` (+`limit?`) | typed read results | user-scoped |

Developer Mode inputs travel as `DeveloperSnapshotWire` — a field-for-field
mirror of the internal `DeveloperContext`; the adapter copies, never infers.

## Guarantees (regression-tested)

- Every exit path is a typed `ApiResponse` — the adapter never leaks a raw
  exception or stack trace (internal failures become `internal_error` with only
  the exception class name in `details`).
- `describe`, `reason`, `learning_status`, preferences reads are deterministic.
- Correlation ids and user ownership are preserved end-to-end. A method-level
  `correlation_id` takes precedence over a nested event/feedback correlation;
  the nested value is the fallback when the method value is absent. Every event
  in an `analyze_developer` result belongs to the requesting user.
- `analyze_developer.result.events` contains every event emitted by that
  operation, in emission order: developer events, then `decision.created`, then
  one `action.proposed` per proposal. Each event is delivered to the sink once.
  The result list and sink delivery are two views of the same emissions; a
  client consuming both must deduplicate by `BrainEvent.id`.
- `people_timeline` returns a bounded oldest-first view of active and historical
  person memories, with memory ids, lifecycle status, dates, durability and
  source/correlation evidence.
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

The **stdio JSON-lines daemon** (Slice 3 Part B, `core.transport`) reads one
request per stdin line and writes response/event frames. The completed HTTP
(`core.transport.http`) and WebSocket (`core.transport.websocket`) adapters use
the same `BrainApi.handle()` contract. See
[`docs/stdio-protocol.md`](stdio-protocol.md),
[`docs/http-transport.md`](http-transport.md), and
[`docs/websocket-transport.md`](websocket-transport.md).

Offline generators use
[`contracts/schemas/brain-api.v1.json`](../contracts/schemas/brain-api.v1.json)
or regenerate/verify it with `python -m contracts.api.schema`; see
[`docs/schema-distribution.md`](schema-distribution.md).