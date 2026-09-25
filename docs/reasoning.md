# Reasoning + Intent + Action Planning (Phase 6 + Phase 8 Slice 2)

Lifecycle of one Developer Mode pass, deterministically, offline, with no
auto-execution. Phase 8 Slice 2 closes the context and personalization loop so
a reasoning round can use relevant memories and learned preferences:

```
Memory / Preferences / People
   │   (ContextEngine, Phase 4)
   ▼
Context  ──build_reasoning_context()──▶  ReasoningContext      (distilled, bounded)
                                              │  (typed, user-scoped, deterministic)
Learning / Personalization (Phase 7, explicit rules only)
   │   (LearningProfilePort, read-only)       ▼
   ▼                                 ReasoningEngine.reason(
AssistanceProfile ──build_learning_influence()──▶ LearningInfluence)  ├─ IntentAnalyzer
                                                    │                  ├─ BugDetector
                                                    ▼                  ├─ CodeReviewer
                                              ReasoningResult          └─ TestResultInterpreter
                                                    ▼
                                              ActionPlanner.plan(...)
                                                    ▼
                                              DevModePipeline.run(...)
                                                    ▼
                                              Events (developer.*, decision.created,
                                                      action.proposed)
```

The loop, phase by phase:

```
Context
  ↓
Learning / Personalization
  ↓
Reasoning
  ↓
Intent / Action Planning
  ↓
Events
```

**Learning stays explicit-rule based and is NOT fake ML.** `AssistanceProfile`
only contains honest counted signals (feedback counts, topic affinities,
aggregate preference evidence). Reasoning copies those features into
`LearningInfluence` — it never infers or invents preferences. The single
behavioral effect is conservative: a keyword suggestion that exactly matches a
learned avoid-topic is suppressed. No foundings, decisions or plans are
otherwise altered by personalization.

## Lifecycle (Phase 6 base flow)

```
DeveloperContext
   │  (trusted snapshot: files, changed_files, current_file/line, git_context,
   │   user_context, test_results)
   ▼
ReasoningEngine.reason(context, task=..., reasoning_context=..., learning-port)
   ├─ IntentAnalyzer      → IntentUnderstanding (kind, keywords, target file/line)
   ├─ BugDetector         → BugFinding[]       (per-file source scans)
   ├─ CodeReviewer        → ReviewFinding[]    (project-level, test-coverage)
   └─ TestResultInterpreter → TestResultInterpretation (exact counts, never fabricates)
   ▼
ActionPlanner.plan(context, reasoning, ask_deploy=...)
   └─ ActionPlan (Pure-data ProposedAction[], BrainDecision + correlation_id)
   ▼
DevModePipeline.run(context, ask_deploy=..., reasoning_context=...)
   └─ DevOutcome
      ├─ reasoning  (IntentUnderstanding, BugFinding[], ReviewFinding[],
      │              TestResultInterpretation, context, learning)
      ├─ plan       (ActionPlan + BrainDecision)
      ├─ events     (BrainEvent[]: bug_detected → fix_proposed → test_result
      │              → review_finding → deploy_proposed, shared correlation_id)
      └─ correlation_id
```

## Design rules (from `docs/developer-mode/SPEC.md`, enforced by tests)

1. **Core Brain proposes; Product executes.** Every proposal is pure data
   (`ProposedAction` has no `execute`, no `executed_at`). `requested_permission_level`
   is REQUESTED, never granted. `code.fix`/`deploy` request `EXPLICIT`;
   `run_tests`/`review` request `READ`.
2. **No fabricated findings.** Bug wording is honest ("Possible …", "may throw"),
   confidence is bounded in `(0, 1)`, and line numbers always come from the real
   source scan — never guessed. The LLM (if configured) may only enrich intent
   keywords, never invent locations.
3. **No fabricated test results.** The interpreter only counts what was supplied.
   Green tests / empty result neither implies nor invents a pass.
4. **Deploy is conservative.** `developer.deploy_proposed` is emitted only when
   `ask_deploy=True` AND tests are green AND no high-warrant fix is pending.
   Ask vs silent = explicit Product preference in `ask_deploy`.
5. **Deterministic confidence.** Intent: keyword match strength. Bugs/review:
   fixed per check. Tests: `passed / (passed + failed + errors)`.
6. **Word-boundary intent matching.** `pr`/`bug`/`fix`/`test` never match as
   substrings, so "deploy to production" is DEPLOY, not a false review.
7. **Isolation.** `ReasoningEngine`/`ActionPlanner`/pipeline reject a context
   that is not a `DeveloperContext` and refuse cross-user planning
   (`ReasoningValidationError` / `ActionPlanningError`).
8. **Distilled, never dumped context.** `build_reasoning_context` copies only
   bounded fields (truncated memory content, ordered reference ids,
   user-scoped) — the full `Context` never enters reasoning.
9. **Explicit personalization only.** `LearningInfluence` is a deterministic
   copy of the learned profile; `has_profile=False` when nothing was learned and
   reasoning still works. Avoided topics only suppress exact keyword
   suggestions (see `core/reasoning/profiles.py`).
10. **No learning-state access in Reasoning.** Reasoning depends on the
    read-only `LearningProfilePort`; it never imports a database or a
    `LearningStateRepository`.

## Modules

| module | role |
|---|---|
| `core/reasoning/intent.py` | `IntentAnalyzer` — deterministic keyword intent |
| `core/reasoning/checks.py` | `scan_file` per-file checks (null-deref, div-by-zero, secret, bare-except, TODO, loop-concat) |
| `core/reasoning/bug_detection.py` | `BugDetector` — `FoundIssue` → `BugFinding` |
| `core/reasoning/review.py` | `CodeReviewer` — project review incl. test-coverage |
| `core/reasoning/test_interpretation.py` | `TestResultInterpreter` |
| `core/reasoning/context.py` | `build_reasoning_context` + `ReasoningContext` distillation (Phase 8 Slice 2) |
| `core/reasoning/profiles.py` | `build_learning_influence` — profile → bounded reasoning input (Phase 8 Slice 2) |
| `core/reasoning/ports.py` | `LearningProfilePort` — read-only learning seam (Phase 8 Slice 2) |
| `core/reasoning/models.py` | `ReasoningContext`, `LearningInfluence`, `ReasoningResult.context/learning` |
| `core/reasoning/reasoning.py` | `ReasoningEngine` facade (+ local `UnderstandingPort`, `LearningProfilePort`) |
| `core/actions/planner.py` | `ActionPlanner` — action proposals + `BrainDecision` |
| `core/brain_events/emitter.py` | `BrainEventEmitter` — typed `developer.*` events |
| `core/brain_events/pipeline.py` | `DevModePipeline` / `DevOutcome` — full demo flow |

## Demo

```python
from core import DevModePipeline
from core.understanding.developer import DeveloperContext

ctx = DeveloperContext(
    user_id="usr_demo",
    repository="digital-brain",
    files=[{
        "path": "core/auth/login.py",
        "content": (
            "def get_user():\n    return None\n\n"
            "def render():\n    user = get_user()\n"
            "    print(user.email)\n"
        ),
        "language": "python",
    }],
    changed_files=["core/auth/login.py"],
    current_file="core/auth/login.py",
    git_context={"branch": "main"},
    user_context={"task": "fix the null error in login render"},
    test_results=[
        {"name": "test_login", "status": "failed",
         "message": "Expected user object but received null"},
        {"name": "test_logout", "status": "passed"},
    ],
)

outcome = DevModePipeline().run(ctx, task="fix the null error in login render")

for event in outcome.events:        # bug_detected, fix_proposed, test_result, review_finding
    print(event.type.value, event.payload.get("title") or event.payload.get("summary"))

for action in outcome.plan.proposed_actions:
    print(action.action_type.value, action.requested_permission_level.value)
    # code.fix → explicit, run_tests → read, review → read (never executed)
```

Deploy: `DevModePipeline().run(ctx, ask_deploy=True)` emits
`developer.deploy_proposed` only when tests are green and no fix is pending.

## Closed loop (Phase 8 Slice 2)

```python
from core import build_brain_service
from core.reasoning import build_reasoning_context

svc = build_brain_service(":memory:")

outcome = svc.analyze_developer(ctx, task="fix the null error in login render")
# outcome.reasoning.context   -> ReasoningContext (distilled, user-scoped)
# outcome.reasoning.learning  -> LearningInfluence (explicit, never invented)

result = svc.reason(ctx, task="...")      # read path: Context -> Profile -> Reasoning
```

`ContextEngine` stays independent: it never imports Reasoning; the one-way
adapter lives in `core/reasoning/context.py`. See `docs/brain-service.md`.