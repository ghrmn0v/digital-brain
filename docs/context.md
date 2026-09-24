# Context Engine + Semantic Search (Phase 4)

The layer between Memory/Understanding and future Reasoning:

```
DeveloperContext
    ↓
Understanding (optional Phase 3 port)
    ↓
ContextEngine.build_context(...)
    ↓
Context              →  (Phase 6) Reasoning → ProposedAction / Brain Event
```

## Responsibility

The Context Engine assembles a **bounded, reasoning-ready Context** for a
developer's current session: current code state + the most relevant memories
(previous bug findings, decisions, preferences, project facts). It owns NO
memory storage. It never writes memory and never creates a second database.
Memory stays owned by `core.memory`; Context and Search only query
`MemoryService` through clean ports.

## Architecture

```
MemoryService (owner)
    ↓ list_memories            (port: MemoryStore)
LexicalSemanticSearch          (port: SemanticSearch)
    ↓ ranked ScoredMemory
ContextEngine
    ↓
Context
```

Protocols live in `core/context/ports.py` (`MemoryStore`, `SemanticSearch`,
`UnderstandingPort`) and are runtime-checkable — `MemoryService` and Phase 3
`LLMGateway` satisfy them unchanged.

## Semantic Search abstraction

```
SemanticSearch (port)
├── LexicalSemanticSearch     ← Phase 4 MVP (deterministic, offline, SQLite)
└── EmbeddingSemanticSearch   ← future: embedded + vector store, SAME signature
```

`SemanticSearch.search(SearchQuery) -> list[ScoredMemory]`. The MVP is
`LexicalSemanticSearch`: it reads a user's memories via `MemoryStore`,
tokenizes, and deterministically ranks. A future vector implementation drops in
behind the port with **no change to the ContextEngine public API**.

## Search

`SearchQuery` (validated, always user-scoped): user_id, text, keywords (from
understanding), repository, current_file, status filter (active/historical/any),
top_k.

`ScoredMemory` (traceable result): the full `Memory` plus score, matched_fields,
ranking_reason, repository_match, file_match.

## Ranking

Deterministic and explainable — no ML, no opaque AI. Seven weighted factors,
final score = normalized weighted sum in [0, 1]:

| factor | weight | notes |
|---|---|---|
| lexical | 0.35 | Dice coefficient on token sets |
| repository | 0.20 | exact 1.0 / related 0.8 / other 0.1 / unknown 0.6 / no target 1.0 |
| file | 0.15 | exact 1.0 / same basename 0.8 / other 0.3 / unknown 0.7 |
| importance | 0.12 | memory contract importance |
| recency | 0.10 | `exp(-age_days / half_life)` (half-life 30 days) |
| status | 0.04 | ACTIVE 1.0 / historical 0.3 |
| type | 0.04 | optional per-type weights |

**Relevance gate:** a memory with no lexical, repository or file signal is
deterministically excluded — no-match returns empty, never fabricated.
Every included memory ships a `ranking_reason` like:

```
lex=0.20 repo=1.00(exact) file=1.00(exact) imp=0.90 rec=1.00 st=1.00 type=1.00
```

## Repository-aware retrieval

Metadata conventions are lenient (see `core/context/fields.py`): context reads
optional `metadata["repository"]` and `metadata["file"]` keys. Memories without
project metadata are treated as "unknown" (neutral, not dropped) and rank on
lexical signal alone — no crash, graceful degradation.

## Context assembly

`ContextEngine.build_context(developer_context, *, task, status, context_id)`:

1. Validate identity (user_id from the trusted DeveloperContext only).
2. Resolve current task (explicit arg or `user_context` keys).
3. Optional Phase 3 understanding → query keywords (entities/topics/concepts).
4. Search memories (user-scoped, bounded candidates).
5. Rank + assemble with category lanes:
   `top_memories` (8) + `previous bug findings` (2) + `decisions` (2) +
   `preferences` (2), hard cap `max_total_memories` (16).
6. Return a bounded `Context`.

`Context` keeps the validated `DeveloperContext`, optional `UnderstandingResult`,
`relevant_memories` (ScoredMemory list) and `MemoryId` references for the
category lanes (never duplicates the persistent representation) plus
`relevant_people`, `search_metadata`, `status`, `fallback_used`. Bounds live in
`ContextLimits` (validated at construction).

## Isolation / security

- Every memory query is scoped by the **trusted** `DeveloperContext.user_id`.
- A query from user A can never return user B's memory, even with matching
  repository/file metadata.
- user_id in nested dicts / LLM output is ignored (same anti-spoofing as Phase 3).
- Different-repository memories cannot dominate a repository's results: repo
  "other" is a harsh penalty and unrelated memories are gated out.

## Failure behavior

- Search failure → `SearchError` → `Context(status=DEGRADED)` with current
  context only, real error in `search_metadata.error`; no fabricated memories.
- No relevant memories → `Context(status=CURRENT_ONLY)` with empty lists.
- Missing repository/file metadata → neutral scoring, no crash.
- `build_context` only raises for invalid inputs/types (never on empty results).

## Testing

42 Phase 4 tests: search/ranking (16), engine (14), isolation (6),
traceability (5), end-to-end deterministic (1). The end-to-end test seeds user A
memories across repositories plus a user B duplicate in the same repo/file,
builds a DeveloperContext, and verifies: same-repo+file finding first, unrelated
repo lower/excluded, user B never returned, bounded, deterministic (no LLM).

## How Phase 5/6 consume the Context API

- The whole workflow is `DeveloperContext → (Understanding) → ContextEngine →
  Context → ReasoningEngine → ProposedAction / Brain Event`.
- Phase 6 Reasoning consumes `Context.relevant_memories` (ScoredMemory with
  traceability), the category lanes, and `Context.understanding`.
- Phase 5 People Intelligence can feed `relevant_people` and later rank by
  person relevance; the search port signature is stable.
- Future vector search: implement `SemanticSearch` over a vector store and
  inject it into `ContextEngine` — public API unchanged.