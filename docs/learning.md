# Learning + Personalization (Phase 7)

The deterministic feedback loop that closes the Developer Mode workflow:

```
developer.*  events
        ↓  (Product executes with permission)
Feedback contract (contracts/feedback)   accepted · rejected · ignored · corrected ·
                                        successful · unsuccessful
        ↓
core/learning/FeedbackInterpreter        deterministic Feedback → LearningSignal
        ↓
LearningEngine.record_feedback
   ├─ OBSERVATION memory  (durable, retrievable by future reasoning)
   ├─ aggregated LearningStatus  (LearningStateRepository, bounded)
   ├─ explicit preference learning (via People Intelligence, reuses supersession)
   └─ importance adjustment      (Signals → Memory importance, bounded)
        ↓
PersonalizationEngine.assistance_profile  → AssistanceProfile / nudges
```

There is **no fake machine learning**. Every signal is an honest counted event
with bounded strength; the learning layer stays platform-independent (no UI,
no microphone, no desktop assumptions — it works for PC and Mobile consumers).

## Signal interpretation

`FeedbackInterpreter` maps ONE contract → ONE signal deterministically:

- kind: explicit `metadata["signal"]` override → label (`accepted`, `rejected`,
  `ignored`, `corrected`, `successful`, `unsuccessful`) → OUTCOME/REWARD value
  sign → numeric value sign. An unreadable record raises
  `LearningValidationError` (never silently invents a signal).
- strength: base per kind, scaled by the absolute `value`.
- delta_importance: positive kinds `+0.05·strength`, negative `−0.06·strength`,
  ignored `0`.
- topic: `metadata["topic"]`, else `suggestion:<action_type>`, else none.
- preference hint: extracted from explicit metadata or keyword detection
  (`concise`/`explanation` → EXPLANATION_DETAIL, `test` → TESTING, …).
- tests_were_green: parsed from `metadata["tests_status"]`.

## Aggregate state

`LearningStatus` holds per-user: `signal_counts`, bounded `topics` affinities
(positive/negative/ignored counts, positive rate, direction, cumulated
delta_importance) and `preference_evidence` (belief weights). Persisted by
`SqliteLearningStateRepository` (swappable `LearningStateRepository` port).

## Explicit learning rules (only these)

1. Repeated **acceptance** of a preference hint (≥ 2 positive, rate ≥ 0.6)
   records the matching developer preference (importance grows with evidence).
2. Repeated **rejection** of a topic (≥ 2 samples, positive rate ≤ 0.25)
   records an `avoid:<topic>` preference.
3. **Accepted while tests green** records `fix-accepted-after-tests`.
4. Feedback targeting a `memory_id` adjusts that memory's importance
   (bounded to `[importance_min, importance_max]`).

Preferences go through `PeopleIntelligence.record_preference` → the same Memory
Engine → Context `developer_preferences` already reads them, so future reasoning
sees learned preferences for free.

## Traceability

Raw feedback is persisted as `OBSERVATION` memories (`source=learning`,
metadata carrying the full Feedback + LearningSignal JSON). `feedback_history`
replays them.

## Demo

```python
feedback = Feedback(
    feedback_id="fb_1", user_id="usr_a",
    source=FeedbackSource.PRODUCT, kind=FeedbackKind.EXPLICIT,
    target=FeedbackTarget(action_id="act_1"),
    label="rejected", value=-1.0, correlation_id="corr_1",
    created_at=now, metadata={"action_type": "code.fix"},
)
engine = LearningEngine(memory, writer=memory, state=SqliteLearningStateRepository(":memory:"),
                        people=PeopleIntelligence(memory, writer=memory))
engine.record_feedback(feedback)          # → StoredFeedback (trace + signal)
engine.feedback_history("usr_a")          # deterministic replay
engine.learning_status("usr_a")           # counts, affinities, evidence
engine.personalization_profile("usr_a")   # AssistanceProfile + nudges for clients
```

End-to-end (Developer Mode + learning): `tests/test_feedback_loop.py` runs the
pipeline, records rejected/ accepted feedback and asserts the learned signal,
preference and profile — while `ProposedAction` keeps no execution surface.