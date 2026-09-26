# Fly — Session State

> Historical snapshot written 25 Sep 2026. The process IDs, local paths and
> service state below describe that session and are no longer live. The
> architecture notes and the open decisions remain current; see
> `IMPROVEMENT_IDEAS.md` for the measured state of each idea.

## Service topology

- Python brain: `127.0.0.1:8601` — `connectome/`, stdlib-only, Py 3.14
- Spring backend: `:8080`
- Desktop: started by the user with `cd desktop && npm start`
- To stop services, find the PID with `ss -ltnp` and `kill <pid>`. **Do not
  `pkill -f electron`** — it kills unrelated processes.
- A Java toolchain was available in that session (57 Java tests passed). This
  environment has a JRE only, so the Java backend cannot be compiled or tested
  here; verification is static plus the Python and Node suites.

## Tests

- Python: `cd connectome && python3 -m unittest discover -s tests -q`
- Java: `cd backend && mvn test` (requires a JDK)
- Node: `cd desktop && npm test`
- RL uses torch from `connectome/.venv`. NumPy is absent, so torch emits a
  warning but works. The full CUDA wheel (~2.8GB) previously hit a disk quota;
  the CPU index resolved it: `--index-url https://download.pytorch.org/whl/cpu`.

## What was built

- Brain: real adult *Drosophila* mushroom body (FlyWire) —
  `adult_mb_wiring.json`, 2414 neurons, rate-model (not AI).
- Phases A–D: influence gate, API auth token interceptor, Retryer, sound
  handling, with tests.
- Phase E (2D billboard):
  - Camera `(0,1.5,7.0)`, billboard height 0.62. An animation offset
    accumulation bug was fixed (eased base `runtime.pos` plus a per-frame
    `extra`, `fly.position.copy(runtime.pos).add(extra)`), together with
    screen-space clamping (`project(camera)` → NDC clamp → `perNdc`), so the
    sprite never slides under the HUD or panels.
  - The speech bubble is now **above the head** (`#speech-bubble` with an
    `::after` caret, projected and clamped).
- Flight system:
  - Server `--flight off|on` (env `FLY_FLIGHT_MODE`, default **on**); local
    GET/POST `/mode`; Spring `BehaviorGateway.flightMode()/setFlight` and
    `FlyController` GET+POST `/api/v1/mode/flight`; a desktop `#flight-mode`
    checkbox kept in sync with a toast.
  - **Celebration flight** (policy.py): flight ON plus a natural
    `SUCCESS/CURIOUS/LEARNING` plus priority ≥ `FLIGHT_MIN_PRIORITY=0.3`
    yields the decision `FLYING`; the desktop plays the
    `TAKEOFF→FLYING→LANDING→IDLE` chain. Serious events
    (IMPORTANT/ERROR/WARNING) never trigger flight. With
    `decide(..., flight=False)` the states drop out of `FLIGHT_STATES`.
  - A previous design was tested and discarded: a flat reward bonus could not
    make FLYING beat the natural boost, and a flat bonus also made serious
    events fly. Celebration flight was chosen instead.
- Live training (API round trip): 7 rounds ×
  {process_completed@0.7, app_open@0.6, notification@0.7} `reacted_positive` →
  dataset +21 labelled.
- Live checks: `process_completed@0.85→FLYING`, `app_open@0.5→FLYING`,
  `important_message@0.92→IMPORTANT`, `warning@0.9→WARNING`,
  `app_idle@0.2→IDLE`, health `flight_mode:"on"`, `/mode/flight` round trip.
- Dataset export: `python3 -m connectome.training.dataset --db <path>` →
  `connectome/training/datasets/train_decisions.{csv,jsonl}` plus
  `dataset_meta.json`.

## Phase 7 (offline RL) — findings and what remains

- Ran: `python -m connectome.training.rl.offline_exp --episodes 4000` → warm-up
  3.37s, **80%** agreement against the prototype table (audio DIFF). Checkpoint
  `connectome/training/rl/experiments/brain_model.pt`, report
  `rl_experiment_latest.json`.
- Then: `python -m connectome.training.evaluation` → **verdict:
  COLLECT_MORE_DATA**, `safe_to_influence_production: False`, no degradation
  (mean_reward_delta 0.0).
- **The mismatch (open problem):**
  - `offline_exp` trains the RL against the fixed table
    `rl_brain.baseline_behavior(type_code)` (image→frontflip,
    sticker→backflip, text/audio→face_user).
  - The **real** production baseline `evaluation.baseline_reactions()` runs the
    real brain, so the `STATE_REACTION` map returns `face_user` for all five
    scenarios.
  - The RL therefore sits at roughly 20% against the real brain, and the gate
    can never say CANDIDATE even though nothing degraded.
- **Open decision for the owner:**
  - (a) aim the RL objective at the real brain's decisions (fix `offline_exp`
    and update `test_rl_experiment.py`) and re-run, targeting CANDIDATE;
  - (b) collect more real feedback in the app without touching the pipeline;
  - (c) `FLY_LEARNED_INFLUENCE=on` without passing the gate (against the design,
    **not recommended**).
  - This was put to the user and dismissed, so it is still the first open
    question.
- `FLY_LEARNED_INFLUENCE=auto` must only open on a verdict of
  `CANDIDATE_FOR_PRODUCTION`.

## Remaining work

1. Phase 7: choose (a), (b) or (c). Correcting the RL objective against the real
   brain is the soundest option.
2. Visual check of the desktop by the owner: bubble above the head, no edge or
   border clipping, and the flight checkbox driving
   TAKEOFF→FLYING→LANDING.

## Key files

- `connectome/connectome/policy.py` — `FLIGHT_STATES`, `FLIGHT_CELEBRATION`,
  `FLIGHT_MIN_PRIORITY`, the celebration override in `decide()`, `NATURAL_STATE`,
  `PRIORITY_LEVEL`, `PATTERNS`
- `connectome/connectome/server.py` — `--flight`, `FlyBrainService(flight=...)`,
  GET/POST `/mode`, health `flight_mode`, `flight` in the result
- `connectome/tests/test_policy.py`, `test_server.py`
- `connectome/connectome/training/rl/offline_exp.py` + `rl_brain.py` — the RL
  pipeline, where the objective mismatch lives
- `connectome/connectome/training/evaluation.py` — the main comparison and the
  `evaluation_reports/evaluation_latest.json` verdict
- `connectome/connectome/training/dataset.py` — DB → dataset export
- `desktop/src/renderer.js` — `runtime.pos` separation, `playState`,
  `runtime.flightChain`, `positionBubble`, screen clamp, `#flight-mode`,
  `demoDecision` flight map
- `desktop/src/animations.js` — FLYING/TAKEOFF/LANDING specs, the `fly_circle`
  eight-figure path
- `desktop/src/index.html` — `#flight-mode`, `#speech-bubble` (+ caret), `#msg`,
  `#toast`
- `backend/.../gateway/BehaviorGateway.java` (+ `Retryer.java`),
  `backend/.../api/FlyController.java`, `DeveloperController.java` — the HTTP
  bridge
- `desktop/models/fly.png` — large; compressing it would help load time

## Notes

- The model cannot read images, so visual verification needs a human. Renderer
  `localStorage` `fly.debug` instrumentation was used for diagnosis; temporary
  capture and debug scripts were removed.
