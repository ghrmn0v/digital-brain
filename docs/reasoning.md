# Reasoning + Intent + Action Planning (Phase 6)

Lifecycle of one Developer Mode pass, deterministically, offline, with no
auto-execution:

```
DeveloperContext
   │  (trusted snapshot: files, changed_files, current_file/line, git_context,
   │   user_context, test_results)
   ▼
ReasoningEngine.reason(context, task=...)
   ├─ IntentAnalyzer      → IntentUnderstanding (kind, keywords, target file/line)
   ├─ BugDetector         → BugFinding[]       (per-file source scans)
   ├─ CodeReviewer        → ReviewFinding[]    (project-level, test-coverage)
   └─ TestResultInterpreter → TestResultInterpretation (exact counts, never fabricates)
   ▼
ActionPlanner.plan(context, reasoning, ask_deploy=...)
   └─ ActionPlan (Pure-data ProposedAction[], BrainDecision + correlation_id)
   ▼
DevModePipeline.run(context, ask_deploy=...)
   └─ DevOutcome
      ├─ reasoning  (IntentUnderstanding, BugFinding[], ReviewFinding[],
      │              TestResultInterpretation)
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

## Modules

| module | role |
|---|---|
| `core/reasoning/intent.py` | `IntentAnalyzer` — deterministic keyword intent |
| `core/reasoning/checks.py` | `scan_file` per-file checks (null-deref, div-by-zero, secret, bare-except, TODO, loop-concat) |
| `core/reasoning/bug_detection.py` | `BugDetector` — `FoundIssue` → `BugFinding` |
| `core/reasoning/review.py` | `CodeReviewer` — project review incl. test-coverage |
| `core/reasoning/test_interpretation.py` | `TestResultInterpreter` |
| `core/reasoning/reasoning.py` | `ReasoningEngine` facade (+ local `UnderstandingPort`) |
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