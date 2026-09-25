# BrainService — Application-Service Boundary (Phase 8, Slice 1)

`BrainService` (`core/service/brain_service.py`) is the **first stable,
platform-independent entry point above the Core Brain modules**. It coordinates
ingestion, memory, understanding, context, people, learning, reasoning, action
planning and developer events through typed Python methods — callers no longer
need to know internal module structure.

It is deliberately **not** an HTTP/WebSocket/SDK layer yet. It is the clean
internal boundary that **later** slices expose to PC and Mobile clients.

## Why it exists

- one stable facade instead of reaching into `core.*` packages;
- real state transitions become emitted Brain Events (see
  `docs/brain-events.md`);
- user isolation + correlation propagation enforced at a single boundary;
- no UI/HTTP/device assumptions anywhere in the layer (guard-tested).

## Construction

```python
from core import build_brain_service, CollectingEventSink

# one SQLite file (or ":memory:") wiring memory + receipts + learning state
service = build_brain_service("data/brain.sqlite3", sink=CollectingEventSink())
```

Manual construction injects the modules you want:

```python
from core.service import BrainService
from core import MemoryService, IngestionService, PeopleIntelligence, ...
BrainService(
    memory=..., ingestion=..., understanding=..., context=...,
    people=..., learning=..., pipeline=..., sink=...,
)
```

## API (typed, user-scoped)

| method | capability | events emitted |
|---|---|---|
| `ingest(data, *, correlation_id=None)` | ingest a source event | `memory.created` per new memory (duplicates → none) |
| `record_feedback(feedback, *, correlation_id=None)` | feedback → learning | `learning.signal.detected` (+ `preference.updated` when a preference is newly learned) |
| `record_preference(user_id, *, name, value, domain=None, ...)` | write a preference | `preference.updated` |
| `analyze_developer(context, *, task=None, ask_deploy=False, correlation_id=None)` | full developer-mode flow: **Context → Learning Profile → Reasoning → Planning → Events** | the five `developer.*` + `decision.created` + `action.proposed` |
| `reason(context, *, task=None)` | read path — Context → Learning Profile → Reasoning only | — |
| `understand(corpus, *, user_id=None, corpus_id=None)` | structured understanding | — |
| `build_context(developer_context, *, task=None)` | bounded Context | — |
| `preferences / developer_preferences / people_summary(user_id)` | people reads | — |
| `people_timeline(user_id, person_id, *, limit=None)` | chronological active + historical person view with provenance | — |
| `learning_status / feedback_history / personalization_profile(user_id)` | learning reads | — |
| `close()` | release the wiring | — |

API-originated calls may pass `event_source` to preserve the request `Source`
on emitted event envelopes. This does not replace the source of an incoming
`NormalizedSourceEvent` or `Feedback` record.

Every operation keeps `user_id` (validated), `correlation_id` (propagated) and
`source` provenance. Missing capability → `BrainServiceConfigurationError`;
invalid input → `BrainServiceValidationError` (raised before any side effect).
Nothing ever executes external actions.

`people_timeline` is a read-only view over the existing Memory Engine history.
It does not mutate, merge or delete person records; superseded memories remain
inspectable with their memory id, lifecycle status, validity dates, durability
classification and source/correlation evidence. Durability stays
`unspecified` when structured evidence is insufficient. Product renders the
returned data; Core owns no timeline UI.

## Platform independence

`core/service/` and `core/brain_events/` contain **no** UI, HTTP, WebSocket,
device or mobile/PC-specific logic (regression-tested). Future slices add:
versioned client-facing API (JSON/RPC), transport adapters as `EventSink`
implementations, and SDK packaging — all outside these modules.

Phase 8 Slice 3A added exactly that **API contract** to the picture without
attaching a transport: `contracts/api` (wire envelope + typed params/results)
and `BrainApi` (adapter in `core/service/api.py`). A client sends an
`ApiRequest`; `BrainApi.handle()` returns an `ApiResponse` for every path. No
listener or transport lives in the service boundary — the stdio JSON-lines
daemon and HTTP/WebSocket adapters consume `BrainApi.handle()` externally.
See `docs/brain-api.md`.

## Closed feedback loop (Phase 8 Slice 2)

`analyze_developer` now runs the normative flow:

```
Context            (ContextEngine.build_context → build_reasoning_context)
  ↓
Learning Profile   (read-only LearningProfilePort → build_learning_influence)
  ↓
Reasoning          (ReasoningEngine.reason, attaches reasoning.context/learning)
  ↓
Intent / Action Planning   (ActionPlanner)
  ↓
Events             (developer.* via pipeline + decision.created/action.proposed)
```

`reason(...)` is the read-only slice of the same flow (no planning, no events).
The Learning layer stays explicit-rule based — no fake ML — and Reasoning only
copies learned features and suppresses exact avoid-topic keyword matches.