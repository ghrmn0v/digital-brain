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
| **Connectome / Fly** | Fly | WhatsApp → Fly pipeline, Spring Boot backend, Python RL / behavior engine, feedback & reward signals, Electron, Three.js Fly |

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
core/                 Phase 1 — Core Brain implementation
  memory/             Memory Engine (deterministic lifecycle, SQLite storage)
docs/memory_engine.md Memory Engine design
tests/                contract + engine validation (stdlib unittest)
pyproject.toml        package metadata (one dependency: pydantic)
CONTRACTS.md          ownership boundaries + versioning + execution rule
```

## Current development phase

Phase 1 — **Memory Engine** (in progress). Built: deterministic classification,
confidence, importance baseline, temporal validity, conflict resolution
(supersession), SQLite persistence behind a repository port, filtered
retrieval, user isolation. Not built yet: LLM integration, embeddings/vector
search, reasoning, context, feedback/learning, frontend, connectors.

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