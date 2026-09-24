# Memory Engine (Core Brain — Phase 1)

Deterministic memory lifecycle. No LLM, no embeddings, no vector search.

## Responsibility

`core/memory.MemoryService` owns the full lifecycle of Brain-owned memories:

```
candidate
  → validate          (non-empty content, confidence/importance bounds)
  → classify          (deterministic → MemoryType, Phase-0 enum)
  → confidence        (preserve provided; else provenance baseline)
  → importance        (documented rule table in [0,1])
  → temporal setup    (created_at/updated_at = now, valid_from, state)
  → persist           (via MemoryRepository port)
  → conflict resolve  (supersede same-domain active memories)
```

## Module structure

```
core/memory/
  candidate.py          MemoryCandidate (relaxed engine input)
  classifier.py         deterministic classification rules
  confidence.py         confidence preservation + provenance baselines
  importance.py         importance rule table (baseline, not ML)
  temporal.py           valid_from/valid_until rules, active/historical state
  conflicts.py          conflict-key derivation + supersession
  filters.py            MemoryQuery + MemoryStatusFilter
  repository.py         MemoryRepository port (storage-agnostic)
  sqlite_repository.py  SQLite implementation of the port
  service.py            MemoryService — public API
  exceptions.py         MemoryEngineError hierarchy
```

## Public API

`MemoryService(repository, *, classifier=None, now=None)`

| Method | Purpose |
|---|---|
| `create_memory(candidate)` | full pipeline, returns stored `Memory` |
| `get_memory(user_id, memory_id)` | single record (raises `MemoryNotFoundError`) |
| `update_memory(user_id, memory_id, **fields)` | partial update, `updated_at` refreshed |
| `supersede_memory(user_id, memory_id, *, superseded_by, happened_at)` | explicit supersession (idempotent) |
| `delete_memory(user_id, memory_id)` | hard delete |
| `list_memories(query)` | filtered retrieval |
| `retrieve_relevant_memories(user_id, *, memory_type, person_id, importance_min, text, limit)` | active, ranked by importance → recency (the future semantic-search seam) |

All reads/writes are scoped by `user_id` — data isolation is enforced by the
repository interface itself.

## Classification rules (deterministic)

Uses only the Phase-0 `MemoryType` enum. Spec names map as:
`PERSON → FACT`, `TASK_CONTEXT → EPISODE`, `OTHER → OBSERVATION`.

First match wins: explicit `candidate.type` → `metadata["kind"]`
(preference/relationship/interaction|conversation/episode|task|task_context/
event/fact; unknown → OBSERVATION) → `metadata["temporary"]` → default `FACT`.

## Confidence rules

Explicitly provided confidence is always preserved. Otherwise:

| signal | value |
|---|---|
| `metadata["explicit"]` or provider `user` | 0.95 |
| structured external (linkedin/whatsapp/calendar/tasks/jobs/product) | 0.70 |
| `metadata["inferred"]` | 0.50 |
| `metadata["conflicting_evidence"]` | 0.40 |
| unknown / no source | 0.60 |

## Importance rules (baseline, not ML)

Base 0.5; additive: PREFERENCE +0.25, RELATIONSHIP +0.20, EVENT +0.10,
INTERACTION −0.10, has related_people +0.10, `explicit` +0.15,
`major_event` +0.20, `temporary` −0.30, confidence ≥ 0.9 +0.05; clamped. An
explicitly provided importance wins (future-learning seam).

## Temporal validity

- `valid_from`/`valid_until` bound truth-period; `valid_until=None` = still
  valid. `valid_until < valid_from` is rejected (`TemporalValidityError`).
- Active = `status == ACTIVE` and not expired. Expired or superseded =
  historical. Historical data is never erased.

## Conflict resolution

Conflicts are scoped to a *conflict key* — no generic all-vs-all conflicts.
Key derivation (first match): explicit `metadata["conflict_key"]`; else
domain table (employment/location/preference/relationship, see
`conflicts.py`). A new memory supersedes every ACTIVE memory with the same
key: old keeps id/content, becomes `SUPERSEDED`, `valid_until` bounded to the
successor's start (never extended), `superseded_by` set.

Company A → Company B: A stays stored and retrievable (historical), B becomes
the active fact.

**Not detectable in Phase 1:** natural-language conflicts, semantic
similarity, or topics without the metadata hints. A future Understanding
module will emit an explicit `conflict_key`.

## Retrieval capabilities

Deterministic filters via `MemoryQuery`: user (required), memory type, person,
status (active/historical/any), importance min, source provider, lexical
`text` substring, created-time range, limit/offset. No embeddings.

## Repository abstraction

`MemoryRepository` is a port. Phase 1 ships `SqliteMemoryRepository`
(data/brain.sqlite3 by default, `:memory:` supported), replaceable later
without touching the service. Proven by tests with an in-memory fake repo.

## Intentionally NOT in Phase 1

LLM integration, embeddings/vector/semantic search, reasoning, intent,
action planning, feedback/learning, connectors, Fly/Connectome, UI, and any
message broker.