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
| `resolve_person` | `user_id`, `name`, optional `aliases`, `correlation_id?` | `PersonResolutionWire` | `person.created` only for a new identity |
| `search` | `user_id`, `text?`, `keywords?`, `memory_type?`, `person_id?`, `importance_min?`, `limit?`, `correlation_id?` | `SearchResultWire` | this user's memories, ranked, with provenance |
| `chat` | `user_id`, `message`, optional `session_id`/`limit`/`target_event_id`/`record_learning`/`correlation_id` | `ChatResultWire` | one grounded turn; cites the memories it used |

Developer Mode inputs travel as `DeveloperSnapshotWire` — a field-for-field
mirror of the internal `DeveloperContext`; the adapter copies, never infers.

### `search`

The retrieval read path. It exists because the Brain owned ranking and
isolation all along but published no way to reach them: `build_context` reports
*how many* memories are relevant, never *which*. Each hit carries `score`,
`matched_fields`, `ranking_reason`, source provenance, `person_ids`,
`related_event_ids` and the `correlation_id` the memory was created under, so a
caller can trace an answer back to the event that caused it.

`user_id` is required and is applied in SQL, so it cannot be widened by a
caller. An empty `text` with no keywords lists by importance and recency rather
than returning nothing.

### `chat`

One conversational turn over the user's own Brain state: retrieve, then answer,
then report what the answer rests on. `grounded_in` lists the memories used, and
is empty exactly when the Brain had nothing to answer from — that is the honest
signal that an answer is ungrounded, as opposed to merely short.

`provider` and `fallback_used` are always present, so a caller can always
distinguish a model answer from a deterministic one.

**A chat answer is never stored.** Learning is recorded only when the caller
supplies `target_event_id`, because the Brain does not invent traceability ids
for interactions it did not observe. Anything the model returns is routed
through the existing Learning Engine like any other evidence, never written
directly as a memory or preference.

## Guarantees (regression-tested)

- Every exit path is a typed `ApiResponse` — the adapter never leaks a raw
  exception or stack trace (internal failures become `internal_error` with only
  the exception class name in `details`).
- Input a Core module refuses is always `validation_error`, never
  `internal_error`: `BrainService` translates People/Learning input errors into
  `BrainServiceValidationError` before they reach the adapter, so a
  whitespace-only `user_id`, name, value or `person_id` reports its real reason.
- `describe`, `reason`, `learning_status`, preferences reads are deterministic.
- **A handled request is `ok: true` even when the event was rejected.**
  `ingest` reports `outcome: "accepted" | "duplicate" | "rejected"` with a
  `reason` in the result at HTTP 200, because the *call* succeeded and the
  event's fate is data, not a transport failure. A consumer that treats HTTP
  200 alone as "the event was stored" will silently lose rejected events; read
  `outcome` instead. Rejections are logged at `warning`, so they are visible
  even when a caller ignores the field.
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
- `resolve_person` compares the name **exactly** (normalized case/whitespace):
  a match returns the existing person, an unknown name returns a deterministic
  `per_…` id with `created=true` and `memory_id`, and a name already used by two
  people returns `ok=true` with `ambiguous=true`, `person_id=null` and both ids
  in `candidates`. Ambiguity is data, not an error: nothing is written and no
  person is ever merged. `person.created` is emitted only when a new identity is
  recorded.
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