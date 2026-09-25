# Digital Brain

A personal AI digital brain. External systems (LinkedIn, WhatsApp, Calendar,
Tasks, Jobs) feed a normalized event stream; the **Core Brain** learns a
long-term model about a person's people, relationships, preferences and intent,
proposes actions, and the product layer executes them — all behind permission
checks.

```
EXTERNAL WORLD → CONNECTORS → normalized events → CORE BRAIN
                → brain events / decisions → PRODUCT & FLY
```

## Team responsibilities

| Area | Owner | Scope |
|---|---|---|
| **Core Brain** | Hüseyn | Memory, context, people, relationships, semantic search, reasoning, intent, action planning, preferences, importance, feedback, learning, personalization, brain events, decisions |
| **Product / Connectors** | Ayxan | LinkedIn / Calendar / Tasks / Jobs connectors, permissions, automation, action execution, main UI, dashboard, People / Memory / Timeline / Jobs views |
| **Connectome / Fly** | Sadeddin | WhatsApp → Fly pipeline, Spring Boot backend, Python RL / behavior engine, feedback & reward signals, Electron, Three.js Fly |

## Repository structure

```
contracts/            Phase 0 — shared, versioned data contracts (Pydantic v2)
  common/             envelope, ids, primitives
  events/             NormalizedSourceEvent (entering the Brain)
  memory/             Memory contract (temporal validity, supersession)
  people/             Person + external identities
  decisions/          BrainDecision / ProposedAction (Brain proposes)
  feedback/           Feedback (source × kind, not all reward)
  brain_events/       typed Brain events
  api/                v1 envelope, public method registry, frames, schema export
  schemas/            packaged deterministic brain-api.v1.json artifact
core/                 Phases 1–8 — Core Brain implementation
  memory/             Memory Engine (deterministic lifecycle, SQLite storage)
  ingestion/          Ingestion pipeline (validation, dedup, receipts, mapping)
  understanding/      LLM Gateway + Understanding (provider abstraction,
                      structured UnderstandingResult, DeveloperContext analysis)
  context/            Context Engine + Semantic Search (deterministic ranking,
                      bounded Context for Reasoning, user isolation)
  people/             People Intelligence (identification, relationships,
                      interaction refs, preferences, developer preferences)
  reasoning/ actions/ brain_events/
                      Reasoning + intent + bug detection, pure-data action
                      planning, and the developer.* Brain events plus the
                      Phase 8 event infrastructure (EventSink / dispatcher)
  learning/           Feedback → deterministic learning → personalization
  service/            Phase 8 BrainService boundary (platform-independent,
                      typed entry point above every module; no UI/transport)
  transport/          Phase 8 stdio JSON-lines, HTTP and WebSocket adapters
                      (BrainApi + EventSink boundaries; transport-only)
docs/memory_engine.md Memory Engine design
docs/ingestion.md     Ingestion pipeline design
docs/understanding.md Understanding / LLM gateway design
docs/context.md       Context Engine / semantic search design
docs/people.md        People Intelligence / preferences design
docs/reasoning.md     Reasoning / intent / action planning / dev pipeline design
docs/learning.md      Feedback / learning / personalization design
docs/brain-events.md  Event infrastructure (EventSink, dispatcher, catalogue)
docs/event-delivery.md consumer-side event delivery contract (identity, ordering,
                      at-most-once, correlation, ownership)
docs/brain-api.md     typed client-facing Brain API contract (contracts/api + BrainApi)
docs/stdio-protocol.md stdio JSON-lines daemon wire protocol (request/response/event frames)
docs/http-transport.md  minimal HTTP transport docs (endpoints, status mapping, events, auth note)
docs/websocket-transport.md bounded user-bound WebSocket protocol and lifecycle
docs/schema-distribution.md canonical v1 JSON Schema distribution for TS/Java
docs/typescript-client.md  thin framework-free TypeScript client (HTTP + WebSocket)
docs/brain-service.md BrainService application-service boundary
docs/developer-mode/  Developer Mode hackathon spec + live doc
clients/typescript/  zero-dependency TypeScript client for both Product clients
PHASES.md             phase tracker (0–7 complete; Phase 8 Slices 1–5A
                      implemented; TS/Java clients remain)
tests/                contract + engine + ingestion + understanding + context
                      + people + reasoning + learning + service tests
pyproject.toml        package metadata (Pydantic + WebSocket server dependency)
CONTRACTS.md          ownership boundaries + versioning + execution rule
```

## Current development phase

Phase 8 — **Platform-independent Brain API/event exposure**. Slice 1 (event
infrastructure + BrainService boundary), Slice 2 (Context + Learning →
Reasoning feedback loop), Slice 3 Part A (the typed client-facing API
contract), Slice 3 Part B (the stdio JSON-lines daemon), Slice 4A (the
minimal HTTP transport), Slice 4B (consumer-side event-delivery guarantees),
Slice 4C (the bounded, user-bound WebSocket transport) and Slice 5A (canonical
v1 schema distribution) are implemented and verified; framework-free TypeScript
and Java clients are NOT started. The Core Brain MVP (Phases 0–7) is
feature-complete and Phases 0–7 plus the completed Phase 8 slices are fully
connected. Built so far:

- Memory Engine (deterministic lifecycle, SQLite, user isolation).
- Ingestion pipeline (validation, dedup, receipts, deterministic mappings,
  atomicity).
- Understanding: provider-independent `LLMGateway` (`understand`, `analyze`,
  `generate_structured`), strict output validation, deterministic offline
  fallback (`heuristic`), configurable provider selection (registry).
- Context: deterministic `LexicalSemanticSearch` behind a `SemanticSearch` port
  (future vector search swaps in without API change), explainable 7-factor
  ranking, repository/file-aware retrieval, bounded `Context` assembly
  (`ContextEngine.build_context`) with bug-finding/decision/preference lanes,
  strict user isolation + anti-spoofing, structured degraded/current-only
  failure behavior.
- People: `PeopleIntelligence` (identification by name/alias tokens,
  relationship facts, interaction-history references, per-person profiles,
  mention-ranked people lists) + preferences (user and developer preferences,
  deterministic domain classification, `record_preference` through the Memory
  Engine with conflict-based supersession, per-domain bounds), plus a bounded
  `people_timeline` view that preserves superseded history, durability labels and
  source/correlation evidence. All views are powerful-user-isolated and
  traceable to memory ids — no second database.
- Reasoning + intent + action planning: deterministic `ReasoningEngine`
  (keyword intent classification with word-boundary matching, source scans for
  null derefs / division-by-zero / secrets / bare `except:`, project review
  with test-coverage, honest test-result interpretation that never fabricates
  pass/fail) + pure-data `ActionPlanner` (fix/run_tests/review/deploy
  proposals request EXPLICIT or READ permission — nothing is ever executed)
  + `DevModePipeline` that emits the five `developer.*` Brain Events with a
  shared correlation id.
- Learning + personalization: deterministic feedback loop — `FeedbackInterpreter`
  maps a Feedback contract to an honest counted signal, `LearningEngine` records
  the trace (memory) + bounded aggregate state and applies ONLY explicit rules
  (repeated acceptance → preference, repeated rejection → `avoid:<topic>`,
  green-test acceptance → testing preference, importance adjustment),
  `PersonalizationEngine` exposes an `AssistanceProfile` for future reasoning
  and clients. No fake ML.
- Event infrastructure (Phase 8 Slice 1): `EventSink` port (transport-independent
  destination — default `NullEventSink`, `CollectingEventSink` for capture);
  emitters for the Brain-owned events (`memory.created`, `preference.updated`,
  `learning.signal.detected`, `decision.created`, `action.proposed`), each tied
  to a real state transition with correlation_id + user ownership + UTC
  timestamps; `BrainEventDispatcher` routes them to a sink; `DevModePipeline`
  optionally dispatches the developer.* events.
- Event delivery contract (Phase 8 Slice 4B): the consumer-side delivery
  semantics are explicit and tested — `BrainEvent.id` is the stable
  per-emission identity (consumer dedup key); within one synchronous
  operation delivery order == emission order (no global ordering, no sequence
  numbers); delivery is in-process at-most-once best-effort (no
  persistence/retry/replay/ack — NOT a durable queue); `correlation_id` lives
  in `payload["correlation_id"]` (always present, `None` when absent); user
  ownership travels on the envelope and consumers must filter by it.
  `EventSink` IS the consumer port — future transports are just sinks.
  See `docs/event-delivery.md`.
- Brain service boundary (Phase 8 Slice 1): `BrainService` — the first stable,
  platform-independent typed entry point above all modules (ingest, understand,
  context, preferences, feedback/learning, developer-mode). It emits real
  transitions to the sink, is user-scoped, and is wired by
  `build_brain_service(...)` (one SQLite file). Nothing executes actions.
- Context + Learning → Reasoning feedback loop (Phase 8 Slice 2): the closed
  pipeline
  `Context → Learning/Personalization → Reasoning → Intent/Action Planning → Events`.
  `build_reasoning_context` distills the bounded `Context` (deterministic order,
  truncated content, user-scoped) into a typed `ReasoningContext`;
  `ReasoningEngine` consults a read-only `LearningProfilePort` and attaches the
  explicit `LearningInfluence` (copied from `AssistanceProfile`, never invented)
  — learned avoid-topics only suppress exact matching keyword suggestions.
  `BrainService.analyze_developer` now runs the whole loop and `BrainService.reason`
  exposes the read path with no events. Learning remains explicit-rule based,
  no fake ML.
- Typed client-facing API contract (Phase 8 Slice 3A): `contracts/api` — a
  versioned, transport-independent wire contract (`ApiRequest` /
  `ApiResponse` envelope, `ApiMethod` registry, typed `params`/`results`,
  typed `ApiError` codes) whose JSON Schemas future TypeScript/Java SDKs
  compile against; `BrainApi` (`core/service/api.py`) adapts every method to a
  `BrainService` call and returns a typed envelope for every exit path —
  including typed errors (`unknown_method`, `version_unsupported`,
  `validation_error`, `not_configured`, `internal_error`). No transport
  attached to the contract itself — transports adapt `BrainApi.handle()`.
- Stdio JSON-lines daemon (Phase 8 Slice 3B): `core/transport` — a
  synchronous, fully dependency-injected daemon that reads one `ApiRequest`
  per stdin line, routes it through `BrainApi.handle()` (still the single
  entry point) and writes one unambiguous JSON-lines frame per stdout line
  (`{"kind":"response","payload":<ApiResponse>}`); a `JsonLinesEventSink`
  adapter streams every emitted `BrainEvent` as `{"kind":"event","payload":<…>}`
  with user_id + correlation preserved. Malformed input yields structured
  typed errors and never terminates the daemon; exceptions never leak
  messages/tracebacks; stdin EOF = clean shutdown. Run:
  `python -m core.transport [--db PATH]`.
- Minimal HTTP transport (Phase 8 Slice 4A): `core/transport/http.py` — a
  stdlib-only (no dependencies) adapter over the same `BrainApi.handle()`
  single entry point. `POST /v1/brain` (one `ApiRequest` JSON → canonical
  `ApiResponse` JSON) and `GET /health` (static liveness). A deterministic
  table maps the existing `ApiErrorCode`s to HTTP statuses (`bad_request` 400,
  `unknown_method` 404, `version_unsupported` 400, `validation_error` 422,
  `not_configured` 503, `internal_error` 500; success 200). Request id,
  version, correlation_id and user isolation are preserved end to end; Brain
  events flow through the service's own EventSink (no second event system;
  the bundled server discards via `NullEventSink`). No authentication is
  invented at this prototype layer (documented; loopback default). Run:
  `python -m core.transport.http [--host 127.0.0.1] [--port 8765] [--db PATH]`.
  See `docs/http-transport.md`.
- Bounded WebSocket transport (Phase 8 Slice 4C):
  `core/transport/websocket.py` — one `/v1/brain?user_id=...` connection is bound
  to one user, every ownership-bearing request is checked against that identity,
  and a service-owned `WebSocketEventRouter` fans events out only to matching
  sockets. Requests still pass through `BrainApi.handle()`; synchronous Core work
  runs off the event loop and is serialized across the shared SQLite service.
  Responses and events reuse the stdio `kind=response|event` envelope. Per-user
  event buffers default to 128 frames with deterministic drop-newest overflow;
  one response remains outstanding and responses are never silently evicted.
  Incoming messages are bounded to 1 MB, browser origins are rejected by default,
  non-loopback binds require an explicit unsafe opt-in, and cancellation waits
  for an already-running worker before releasing the service lock. The identity
  is routing/isolation metadata, **not authentication**; no retry, replay,
  acknowledgement, durable queue or broker is introduced. Run:
  `python -m core.transport.websocket [--host 127.0.0.1] [--port 8766] [--db PATH]`.
  See `docs/websocket-transport.md`.
- Canonical v1 schema distribution (Phase 8 Slice 5A):
  `contracts/api/registry.py` is the public immutable method/model registry used
  by both `BrainApi.describe()` and the offline exporter. `contracts/api/frames.py`
  owns the canonical response/event envelopes, while stdio/WebSocket reuse them.
  `contracts/schemas/brain-api.v1.json` is a deterministic, data-free JSON
  Schema bundle
  with request/response/error/event/frame contracts and ordered refs for all 16
  methods. Generate with `python -m contracts.api.schema`; verify drift with
  `python -m contracts.api.schema --check`. This is the shared generation input
  for framework-free TS/Java clients, not a UI or mobile framework. See
  `docs/schema-distribution.md`.

- Thin framework-free TypeScript client (Phase 8 Slice 6):
  `clients/typescript/` speaks the same contract over HTTP and WebSocket with
  zero runtime dependencies and no Node-only APIs, so one source serves the PC
  browser, the mobile client and Node 22+. It mints request ids, injects the
  caller's identity into ownership params, serializes WebSocket requests (the
  Core allows one outstanding response per connection) and applies the consumer
  event rules: dedupe by `BrainEvent.id`, per-user filtering, correlation-id
  grouping, no replay. Its method table and error codes are verified against the
  canonical schema artifact, and its HTTP tests run live against the real Core
  transport. Run `cd clients/typescript && node --test test/` (no install
  needed). See `docs/typescript-client.md`.

Not built yet: embeddings/vector store, connectors, frontend, and a Java client
package. Mobile Product code remains responsible for
microphone/transcription UX, auth, notifications, push providers and action
execution. Durable/broker delivery (Redis/Kafka/persistent queue, retry workers)
is explicitly NOT part of Phase 8.

## Developer Mode (hackathon)

The MVP workflow targets: context in → Core Brain understands → detects a
potential bug → `developer.bug_detected` → explains → proposes a fix →
Product asks permission → executes → tests interpreted → review findings →
deploy proposed (never auto) → feedback → learning. A ready end-to-end demo
exists: `DevModePipeline().run(developer_context)` produces `developer.bug_detected`
→ `developer.fix_proposed` → `developer.test_result` → `developer.review_finding`
→ (if asked and green) `developer.deploy_proposed`, all correlation-linked and
fully deterministic — see `tests/test_devmode_e2e.py` and `docs/reasoning.md`.
See `docs/developer-mode.md` and `docs/developer-mode/SPEC.md`.

## How contracts are used

- Python teams import the `contracts` package directly.
- TS (Product UI / Fly Electron) and Java (Spring Boot) generators consume
  `contracts/schemas/brain-api.v1.json`; regenerate it with
  `python -m contracts.api.schema` after contract changes.
- Any team-boundary change ships through this repo first. See `CONTRACTS.md`
  and `docs/schema-distribution.md` for compatibility and generation rules.

## Validation

```
python -m contracts.api.schema --check
python -m unittest discover -s tests -t .
```

Requires Python ≥ 3.11, `pydantic>=2.8` and `websockets>=12` (the WebSocket
package is imported lazily by the transport server).
