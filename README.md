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
  transport/          Phase 8 stdio JSON-lines daemon + minimal HTTP transport
                      (BrainApi + EventSink adapters; transport-only, stdlib)
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
docs/brain-service.md BrainService application-service boundary
docs/developer-mode/  Developer Mode hackathon spec + live doc
PHASES.md             phase tracker (0–7 complete; Phase 8 Slices 1–3)
                      in progress → Slices 4A–4B complete)
tests/                contract + engine + ingestion + understanding + context
                      + people + reasoning + learning + service tests
pyproject.toml        package metadata (one dependency: pydantic)
CONTRACTS.md          ownership boundaries + versioning + execution rule
```

## Current development phase

Phase 8 — **Platform-independent Brain API/event exposure**. Slice 1 (event
infrastructure + BrainService boundary), Slice 2 (Context + Learning →
Reasoning feedback loop), Slice 3 Part A (the typed client-facing API
contract), Slice 3 Part B (the stdio JSON-lines daemon) and Slice 4A (the
minimal HTTP transport) are implemented and verified; WebSocket/mobile
transport adapters and SDK packaging are NOT started. The Core Brain MVP
(Phases 0–7) is feature-complete and Phases 0–7 (plus 8.1–8.4A) are fully
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
  Engine with conflict-based supersession, per-domain bounds), powerful user
  isolation, all traceable to memory ids — no second database.
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

Not built yet: embeddings/vector store, connectors, frontend, and the remaining
Phase 8 work — WebSocket/mobile transport adapters (as EventSink/BrainApi
adapters) and SDK packaging (TS/Java from the exported JSON Schemas). The
consumer-side event delivery contract (Slice 4B) is defined and tested;
durable/broker delivery (Redis/Kafka/persistent queue, retry workers) is
explicitly NOT part of it.

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
- TS (Product UI / Fly Electron) and Java (Spring Boot) teams consume the
  exported JSON Schema (`Model.model_json_schema()`).
- Any team-boundary change ships through this repo first. See `CONTRACTS.md`
  for the compatibility rules.

## Validation

```
python -m unittest discover -s tests -t .
```

Requires Python ≥ 3.11 and `pydantic>=2.8` (installed in `.venv`).
