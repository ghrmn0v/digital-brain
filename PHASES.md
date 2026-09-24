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
| 5 | People + Relationships + Preferences (`core/people/`) | ✅ COMPLETE |
| 6 | Reasoning + Intent + Action Planning (`core/reasoning/`, `core/actions/`, `core/brain_events/`) | ✅ COMPLETE |
| 7 | Feedback + Learning + Personalization (`core/learning/`) | ❌ NOT STARTED |

Guiding rules (from SPEC.md, enforced every phase):

- Work incrementally; never destroy Phase 0–2.
- Follow existing architecture/naming; smallest working MVP; no new deps beyond
  Python + Pydantic (SQLite allowed).
- Core Brain PROPOSES, Product EXECUTES after permission. Never auto-execute.
- The existing test baseline (121) must keep passing every phase.
- Do NOT commit or push. Report after each phase and STOP.

## Phase 3 — LLM Gateway + Understanding (complete)

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
  Phase 4: `docs/context.md`; Phase 5: `docs/people.md`.
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

## Phase 5 — People + Relationships + Preferences (complete)

- Added `core/people/`:
  - `exceptions.py` — `PeopleError` / `PeopleValidationError`.
  - `ports.py` — `PeopleMemory` (read) + `PeopleMemoryWriter` (write)
    runtime-checkable ports; `MemoryService` satisfies both unchanged.
  - `identification.py` — deterministic token-based name/alias matching
    (`tokenize`, `collect_aliases`, `identify`); names come from
    `person_name` / `person_aliases` / `name` metadata next to
    `related_people`.
  - `models.py` — `PersonProfile`, `RelationshipFact`, `InteractionReference`,
    `PersonFact`, `PersonSummary`, `PeopleSummary`, `Preference`,
    `PreferenceDomain`, `DeveloperPreferences`, bounded `PeopleLimits`.
  - `intelligence.py` — `PeopleIntelligence`: `identify_people`, `profile`,
    `relationships`, `interactions`, `people_summary`, `preferences`,
    `developer_preferences`, `record_preference`.
- Design decisions:
  - Identity stays the Phase 0 `Person` contract (`PersonId`); NO second
    people DB — everything is derived from Memory Engine records and traceable
    to `memory_id`. People Intelligence owns no storage (same rule as Context).
  - Developer preferences use `PreferenceDomain` (language, coding_style,
    testing, explanation_detail, commit_style, deployment); explicit
    `metadata["domain"]` wins, then a deterministic keyword table; anything
    else is a general user preference (domain=None).
  - `record_preference` writes through the Memory Engine with
    `metadata["preference"] = "<domain>:<name>"` as conflict key → re-recording
    supersedes the old record (distinct domains never collide).
  - Strict user isolation (people/preferences never leak across users).
  - `classify_preference_domain` keeps commit_style before coding_style so
    "conventional commits" maps to commit style, not style/convention.
- Integration: `ContextEngine.build_context` (Phase 4) already exposes
  `developer_preferences` + `relevant_people` from the same memories — both
  views agree by construction (`tests/test_people_context_integration.py`).
- Tests: 30 new (`test_people_intelligence.py`, `test_people_preferences.py`,
  `test_people_context_integration.py`).
- Verification: full suite `216` OK (baseline 186 + 30 new), `compileall` clean.
- Docs: `docs/people.md`, README, `docs/developer-mode.md` updated.
## Phase 6 — Reasoning + Intent + Action Planning (complete)

- Contract additions (additive — existing enum iteration tests stay valid):
  - `contracts/decisions/decisions.py`: `ActionType` += `RUN_TESTS`,
    `CODE_FIX`, `REVIEW`, `DEPLOY`; `PermissionLevel` += `EXPLICIT`.
  - `contracts/brain_events/events.py`: `BrainEventType` += the five
    `developer.*` event types (bug_detected, fix_proposed, test_result,
    review_finding, deploy_proposed) with documented payload shapes.
- Added `core/reasoning/`:
  - `exceptions.py` — `ReasoningError` / `ReasoningValidationError`.
  - `models.py` — `Severity`, `IntentKind`, `ReviewCategory`, `BugFinding`,
    `ReviewFinding`, `TestFailure`, `TestResultInterpretation`, `IntentUnderstanding`,
    `ReasoningResult`, bounded `ReasoningLimits`.
  - `intent.py` — `IntentAnalyzer`: deterministic keyword classification with
    WORD-BOUNDARY matching (short tokens like `pr`/`bug` no longer false-match
    substrings); optional LLM keywords may only enrich, never set target file.
  - `checks.py` — per-file source scans (`scan_file`): null-deref, division by
    zero, secret-literal (regex brace bug fixed — was `{{3,}}` in a non-f-string),
    bare `except:`, TODO/FIXME marker, in-loop string concat; guarded code not
    reported; bounded per-file issues; `FoundIssue` dataclass.
  - `bug_detection.py` — `BugDetector` maps `FoundIssue` → `BugFinding`
    (honest "Possible …" language, bounded confidence < 1, per-finding id).
  - `review.py` — `CodeReviewer`: project-level review (test-coverage for
    changed files missing a test file, bare-except/maintainability), maps to
    `ReviewCategory`.
  - `test_interpretation.py` — `TestResultInterpreter`: summarizes counted
    pass/fail/skip/error EXACTLY as supplied; NEVER fabricates results;
    confidence = passed / (passed + failed + errors).
  - `reasoning.py` — `ReasoningEngine` facade (validates context is a
    `DeveloperContext`, runs intent → bugs → review → tests in one pass; local
    `UnderstandingPort` protocol so reasoning never depends on core.context).
- Added `core/actions/`:
  - `models.py` — `ActionPlan` wraps a contract `BrainDecision`; proposals are
    pure data, no execution surface.
  - `exceptions.py` — `ActionPlanningError` / `ActionValidationError`.
  - `planner.py` — `ActionPlanner`: code.fix/deploy request `EXPLICIT` permission,
    run_tests/review request `READ`; runs tests only when results supplied; deploys
    ONLY when `ask_deploy=True` AND tests green AND no high-warrant fix proposed;
    bounded `max_proposals=5`; shared `correlation_id`; user/mismatch isolation.
- Added `core/brain_events/`:
  - `emitter.py` — `BrainEventEmitter` builds `contracts.brain_events.BrainEvent`
    with deterministic payloads for each developer event type.
  - `pipeline.py` — `DevModePipeline` + `DevOutcome`: reason → plan → events
    (bug → fix → test → review → deploy) sharing one correlation_id. Nothing is
    executed — Core Brain PROPOSES only.
- Design decisions:
  - Repetition of fix proposals is allowed (one per finding) BUT prioritized
    and bounded; review role is a `REVIEW` *action proposal* if findings are
    high-warrant, otherwise only emitted as event.
  - Developer Brain Events wrap contract envelopes purely (id, actor, source).
- Tests: 37 new (`test_reasoning.py`, `test_actions.py`,
  `test_brain_events.py`, `test_devmode_e2e.py`).
- Verification: full suite `253` OK (baseline 216 + 37 new), `compileall` clean.
- Docs: `docs/reasoning.md`, README, `docs/developer-mode.md` updated.
