# Digital Brain — Phase Tracker

Canonical progress file for the Core Brain implementation. Hackathon deadline:
**September 27, 2026**. Saved spec: `docs/developer-mode/SPEC.md`.

| Phase | Area | Status |
|---|---|---|
| 0 | Contracts (`contracts/`) | ✅ COMPLETE |
| 1 | Memory Engine (`core/memory/`) | ✅ COMPLETE |
| 2 | Ingestion Pipeline (`core/ingestion/`) | ✅ COMPLETE |
| 3 | LLM Gateway + Understanding (`core/understanding/`) | ✅ COMPLETE |
| 4 | Context + Semantic Search (`core/context/`) | ✅ COMPLETE |
| 5 | People + Relationships + Preferences (`core/people/`) | ❌ NOT STARTED |
| 6 | Reasoning + Intent + Action Planning (`core/reasoning/`, `core/actions/`) | ❌ NOT STARTED |
| 7 | Feedback + Learning + Personalization (`core/learning/`) | ❌ NOT STARTED |

Guiding rules (from SPEC.md, enforced every phase):

- Work incrementally; never destroy Phase 0–2.
- Follow existing architecture/naming; smallest working MVP; no new deps beyond
  Python + Pydantic (SQLite allowed).
- Core Brain PROPOSES, Product EXECUTES after permission. Never auto-execute.
- The existing test baseline (121) must keep passing every phase.
- Do NOT commit or push. Report after each phase and STOP.

## Phase 3 — LLM Gateway + Understanding (this phase)

- Saved the hackathon MVP spec verbatim to `docs/developer-mode/SPEC.md`.
- Added `core/understanding/`:
  - `exceptions.py` — `UnderstandingError` → `LLMGatewayError` →
    `LLMTimeoutError` / `LLMProviderError` / `InvalidLLMOutputError`.
  - `models.py` — `UnderstandingIntent` enum + validated `UnderstandingResult`
    (entities, intent, topics, salience, confidence, summary,
    relevant_code_concepts).
  - `developer.py` — `DeveloperContext` (transport-independent repo/code input),
    `DeveloperAnalysis` (context analysis output) + `summarize_context()`
    trusted stats.
  - `validation.py` — JSON extraction + strict pydantic validation of raw
    provider output (`extract_json_object`, `parse_understanding`).
  - `providers.py` — `LLMProvider` protocol, `LLMRequest`,
    `HeuristicProvider` (deterministic offline fallback), provider registry.
  - `gateway.py` — `LLMGateway` (`understand`, `analyze`, `generate_structured`),
    `GatewayConfig`, primary→fallback error handling, `build_gateway()`.
- Design decisions:
  - Provider = text completion port; all structuring/validation lives in the
    gateway → raw/unvalidated LLM output can never flow further.
  - Default provider `heuristic` (deterministic, offline) so the MVP runs without
    an API key; real providers register behind the same `LLMProvider` port.
  - `understand`/`analyze` fall back to the heuristic provider on timeout /
    provider failure / malformed output; `generate_structured` never silently
    falls back (no fabricated certainty).
  - `analyze` stamps `user_id` / `repository` / file stats from the trusted
    `DeveloperContext`; values in LLM output never override them (isolation).
- Tests (Phase 3): `tests/test_understanding.py` + `tests/understanding_support.py`.
- Verification: full suite `144` tests OK (baseline 121 + 23 new), `compileall` clean.

## Phase status notes

- Phase 0: see `CONTRACTS.md`; Phase 1: `docs/memory_engine.md`;
  Phase 2: `docs/ingestion.md`; Phase 3: `docs/understanding.md`;
  Phase 4: `docs/context.md`.
- Developer Mode docs: `docs/developer-mode.md` (updated per phase).

## Phase 4 — Context + Semantic Search (complete)

- Added `core/context/`:
  - `ports.py` — `MemoryStore` / `SemanticSearch` / `UnderstandingPort`
    (runtime-checkable; `MemoryService` and `LLMGateway` satisfy them).
  - `fields.py` — lenient metadata conventions (`repository` / `file` / `kind`),
    bug-finding/decision detection, `normalize_repository`.
  - `models.py` — `SearchQuery`, `ScoredMemory` (score + matched_fields +
    ranking_reason + repo/file match), `SearchMetadata`, bounded `Context`
    (category lists reference memories by `MemoryId`), `ContextStatus`
    (full / current_only / degraded), validated `ContextLimits`.
  - `ranking.py` — deterministic 7-factor ranker (lexical Dice, repository,
    file, importance, recency exponential decay, status, type), weighted
    normalized sum, relevance gate (no signal → excluded), `ranking_reason`.
  - `search.py` — `LexicalSemanticSearch` over `MemoryStore.list_memories`,
    store failures → `SearchError`, `top_k` bound.
  - `engine.py` — `ContextEngine.build_context(...)` → bounded `Context`
    (identity validated from trusted DeveloperContext, optional Phase 3
    understanding keywords, category lanes, hard caps, DEGRADED/CURRENT_ONLY).
- Architecture rule: Context Engine owns NO memory; queries MemoryService only
  through ports; future embedding/vector search replaces `LexicalSemanticSearch`
  behind `SemanticSearch` without API change.
- Tests: 42 new (search 16, engine 14, isolation 6, traceability 5, e2e 1).
- Verification: full suite `186` OK (baseline 144 + 42 new), `compileall` clean.
- Docs: `docs/context.md`, README, `docs/developer-mode.md` updated.