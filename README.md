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
core/                 Phases 1–4 — Core Brain implementation
  memory/             Memory Engine (deterministic lifecycle, SQLite storage)
  ingestion/          Ingestion pipeline (validation, dedup, receipts, mapping)
  understanding/      LLM Gateway + Understanding (provider abstraction,
                      structured UnderstandingResult, DeveloperContext analysis)
  context/            Context Engine + Semantic Search (deterministic ranking,
                      bounded Context for Reasoning, user isolation)
docs/memory_engine.md Memory Engine design
docs/ingestion.md     Ingestion pipeline design
docs/understanding.md Understanding / LLM gateway design
docs/context.md       Context Engine / semantic search design
docs/developer-mode/  Developer Mode hackathon spec + live doc
PHASES.md             phase tracker (0–7)
tests/                contract + engine + ingestion + understanding + context tests
pyproject.toml        package metadata (one dependency: pydantic)
CONTRACTS.md          ownership boundaries + versioning + execution rule
```

## Current development phase

Phase 4 — **Context Engine + Semantic Search** (complete). Built so far:

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

Not built yet: people/relationships, reasoning/intent/bug detection, action
planning, feedback/learning, embeddings/vector store, connectors, frontend.

## Developer Mode (hackathon)

The MVP workflow targets: context in → Core Brain understands → detects a
potential bug → `developer.bug_detected` → explains → proposes a fix →
Product asks permission → executes → tests interpreted → review findings →
deploy proposed (never auto) → feedback → learning. See
`docs/developer-mode.md` and `docs/developer-mode/SPEC.md`.

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
