
# TASK: Rebuild the "Fly / Connectome" project from scratch

You are rebuilding an existing, working, 3-layer project called **Fly / Connectome**. It is a
desktop AI-companion: a persistent 3D fly (Electron + Three.js) whose *behavior* is decided by a
Python brain that is a **real rate-model simulation of the adult Drosophila mushroom body**
(FlyWire wiring, 2414 neurons), reached through a Spring Boot service boundary. The fly learns
from user feedback (dopamine-gated three-factor plasticity) and there is an offline-RL + evaluation
+ production-gate pipeline.

Build it **exactly** as specified below. Exact names, exact numeric constants, exact HTTP routes,
exact CLI flags and exact test expectations are all load-bearing — do not "improve" or rename them.

## 0.1 Non-negotiable rules

1. **Python inference engine must be stdlib-only.** No third-party imports in `connectome/*.py`.
   `torch` may appear ONLY inside `connectome/training/rl/rl_brain.py` (guarded by try/except) and
   `connectome/training/rl/offline_exp.py` (imported lazily inside functions). Never import torch in
   `server.py`, `policy.py`, `model.py`, `influence.py`.
2. **Do NOT create git commits or push.** Leave the working tree dirty. Use conventional-commit
   *style* in documentation only.
3. **Never let an untested ML model replace the deterministic baseline.** Production influence is
   gated (see §2.9). Default verdict must keep the gate shut.
4. **No new technologies** beyond: Python stdlib, Java 21 + Spring Boot, Electron + Three.js,
   Node (whatsapp-gateway). No Lombok, no Spring Security, no JPA, no Docker, no React.
5. **Training code must never live in the production request path** (`connectome/training/` is
   separate from the inference modules).
6. Secrets come from env vars only, never hardcoded, never committed.
7. Every state/behavior name, threshold and route string below is case-sensitive and exact.

## 0.2 Repository layout

```
/repo
├── README.md
├── .gitignore
├── connectome/                      # Python brain + training (stdlib-only inference)
│   ├── pyproject.toml
│   ├── connectome/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── model.py
│   │   ├── policy.py
│   │   ├── event_processor.py
│   │   ├── state_machine.py
│   │   ├── simulate.py
│   │   ├── store.py
│   │   ├── influence.py
│   │   ├── reward.py
│   │   ├── server.py
│   │   ├── data/adult_mb_wiring.json
│   │   ├── reference/flywire_live_service.py   # legacy, not imported anywhere
│   │   └── training/
│   │       ├── __init__.py
│   │       ├── analysis.py
│   │       ├── dataset.py
│   │       ├── evaluation.py
│   │       ├── datasets/                       # git-ignored artifacts
│   │       ├── evaluation_reports/             # git-ignored artifacts
│   │       └── rl/
│   │           ├── __init__.py
│   │           ├── rl_brain.py
│   │           ├── offline_exp.py
│   │           └── experiments/                # git-ignored artifacts
│   └── tests/                       # 12 unittest files, 99 tests
├── backend/                         # Spring Boot 3.3.5, Java 21, Maven
└── desktop/                         # Electron 33 + Three.js 0.169
    ├── package.json
    ├── src/{index.html,main.js,preload.cjs,renderer.js,animations.js,sound.js,developer.js}
    ├── test/{animations,developer,sound}.test.mjs      # node --test, 20 tests
    └── models/{fly.png, Fly_uv_Lowpoly.obj, Fly_uv.jpg}
└── whatsapp-gateway/{package.json,server.js}
```

`pyproject.toml`: name `fly-connectome`, version `0.1.0`, `requires-python >= 3.11`,
package-data `connectome/data/*.json`.

`.gitignore` must ignore (among others):
```
connectome/connectome/training/rl/experiments/*.pt
connectome/connectome/training/rl/experiments/*.json
connectome/connectome/training/evaluation_reports/*.json
connectome/connectome/training/datasets/
desktop/node_modules/
desktop/models/fly.png
```

---

# PART 1 — PYTHON BRAIN

## 1.1 `connectome/__init__.py`
Re-export surface, `__version__ = "0.1.0"`:
```python
from connectome.loader import WiringGraph, load_wiring, default_wiring_path
from connectome.model import Brain
from connectome.event_processor import normalize_event, normalize_feedback, Event
from connectome.state_machine import StateMachine, states
from connectome.policy import decide
from connectome.reward import map_feedback, RewardSignal
__all__ = ["WiringGraph","load_wiring","default_wiring_path","Brain",
           "normalize_event","normalize_feedback","Event","StateMachine","states",
           "decide","map_feedback","RewardSignal"]
```

## 1.2 `connectome/data/adult_mb_wiring.json`
FlyWire adult mushroom-body wiring. `meta` = `{name, neurons}` where `neurons == 2414`.
Structure:
```json
{ "meta": {"name": "...", "neurons": 2414},
  "nodes": [ {"id": "KC_...", "population": 1, "type": "kc"}, ... ],
  "edges": [ {"from": "KC_...", "to": "MBON_...", "synapses": 3, "plastic": true}, ... ] }
```
Node `id` prefixes: `PN`, `KC*`, `DAN_PAM`, `DAN_PPL`, `CTX`, `MBON_*`, `MBF`.
Node `type` values include `kc`, `mbon`, `dan`, `pn`, `ctx`, `mbf`.
Exactly 7 MBON compartments: alpha, beta, beta2, gamma, apostrophe, bpost, output.
Exactly 7 `plastic: true` edges, all `KC -> MBON_*`.
`meta.name` is returned by `/health` as `graph`; `meta.neurons` as `neurons`.

## 1.3 `connectome/loader.py`
```python
DEFAULT_WIRING = "data/adult_mb_wiring.json"
def default_wiring_path() -> Path      # Path(__file__).parent / DEFAULT_WIRING  (package-relative!)
```
Dataclasses: `Edge(source, target, synapses, plastic, physiology="excitatory", weight=1.0)`
with `@property key -> (source, target)`; `NodeGroup(id, population, type)`;
`WiringGraph(meta, nodes: dict, edges: dict)` with `group(gid)`, `incoming(gid)`, `outgoing(gid)`,
`plastic_edges()`, `total_incoming_synapses(gid)`, `validate()`.

`load_wiring(path=None)`: read `utf-8`, `json.loads`; `nodes` from `data["nodes"]`
(**required key**), `edges` from `data.get("edges", [])`; **JSON uses `"from"`/`"to"` keys**
mapped to `source`/`target`; `int(node["population"])`, `float(edge["synapses"])`; edges keyed by
`(source,target)` (duplicates overwrite silently); then `validate()`.

`validate()` raises `ValueError` for: non-positive population, edge endpoint missing from nodes,
non-positive synapse count. `incoming`/`outgoing` are linear scans (no adjacency index) — keep it
simple, matching semantics matters more than speed. `total_incoming_synapses` includes DAN→KC
modulatory edges and is the normalizer in `Brain._drive`.

## 1.4 `connectome/model.py` — the rate-model brain
```python
DEFAULT_CONFIG = {
    "dt": 0.5, "tau": 4.0, "kc_theta": 0.35, "eta": 0.004,
    "weight_max": 4.0, "weight_min": 0.05,
    "decay": 0.0005, "noise": 0.0005,
}
```
`Brain(graph, config=None)`: merges config over `DEFAULT_CONFIG`; `activity`, `inputs`, `weights`
(from `edge.weight`), `dan_gate=0.0`, `dan_sign=0`.

Activation function — **dispatch by `gid` string prefix**, not by `NodeGroup.type`:
```python
if gid.startswith("KC"):                                  # exponential rectifier
    theta = config["kc_theta"]
    return 0.0 if drive <= theta else 1.0 - math.exp(-(drive - theta))
if gid.startswith("DAN") or gid.startswith("PN") or gid == "CTX":   # clipped linear
    return max(0.0, min(1.0, drive))
return math.tanh(max(0.0, drive))                        # MBON_*, MBF (max ~0.7616)
```

Drive:
```python
total = sum(edge.synapses * self.weights[edge.key] * self.activity[edge.source]
            for edge in graph.incoming(gid))
scale = graph.total_incoming_synapses(gid) or 1.0
drive = self.inputs[gid] + total / scale
return max(0.0, min(1.0, drive + config["noise"]))       # noise is a CONSTANT +0.0005 bias
```
`set_input(gid, v)` clamps to `[0,1]`. `clear_inputs()` rebuilds all-zero (this WIPES DAN drive —
important ordering constraint below).

`step()` — synchronous (Jacobi): compute all targets first, then
`activity[gid] += (dt/tau) * (target - activity[gid])`; `dt/tau == 0.125`. Then `_update_plasticity()`.

`_update_plasticity()` — three-factor, one-shot (gate is consumed at the end):
```python
gate = self.dan_gate
if gate <= 1e-9: return
for edge in graph.plasticity_edges():                 # only plastic=True (KC -> MBON_*)
    kc   = self.activity.get(edge.source, 0.0)
    mbon = self.activity.get(edge.target, 0.0)
    delta = cfg["eta"] * gate * kc
    if self.dan_sign >= 0:
        delta *= (1.0 - mbon)                        # anti-Hebbian: unused synapses grow
    else:
        delta = -cfg["eta"] * gate * kc               # depression
    w = self.weights[key] + delta
    w -= cfg["decay"] * (self.weights[key] - 1.0)     # decay uses the OLD weight
    self.weights[key] = clamp(w, cfg["weight_min"], cfg["weight_max"])
self.dan_gate = 0.0
self.dan_sign = 0
```

`deliver_reward(value)`: clamp `value` to `[-1,1]`; `dan_gate = abs(value)`;
`dan_sign = 1 if value >= 0 else -1`; then set input `DAN_PAM = abs(value)`, `DAN_PPL = 0`
(for positive) or the reverse (for negative).

`mbon_vector()` → `{gid: activity[gid] for gid, g in graph.nodes.items() if g.type == "mbon"}`
(7 entries). `synapse_weight(src, tgt)`. `reset()` zeroes activity/inputs/gate/sign but **keeps
weights**.

**Ordering constraint (must be documented in code comments and honored by all callers):**
`inject_event()` → N×`step()` → `deliver_reward()` → 3×`step()`. Calling `clear_inputs()` between
`deliver_reward` and `step` destroys the DAN gate's effect.

## 1.5 `connectome/event_processor.py`
```python
@dataclass
class Event:
    id: str; name: str; source: str; priority: float
    person: Optional[Dict[str, Any]]; context: Dict[str, Any]; timestamp: float
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

@dataclass
class Feedback:
    id: str; behavior_id: str; feedback: str
    timestamp: float; context: Dict[str, Any]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

KNOWN_EVENTS = frozenset({"important_message","notification","user_message","task_reminder",
    "calendar_event","process_completed","process_failed","warning","app_open","app_idle","unknown"})
KNOWN_SOURCES = frozenset({"whatsapp","core_brain","calendar","tasks","linkedin","app",
    "connectors","unknown"})
FEEDBACK_TYPES = frozenset({"looked","interacted","ignored","dismissed","opened_related",
    "marked_useful","marked_unnecessary","reacted_positive","reacted_negative"})

normalize_event(raw) -> Event      # normalize_feedback(raw) -> Feedback
is_feedback(raw) -> bool           # raw.get("event") == "fly_feedback"
```
Normalization rules (exact):
- Inbound key for the event name is **`"event"`**, not `"name"`.
- `id = str(raw.get("id") or uuid4())` — falsy/absent → fresh UUID.
- `name`: must be `str` **and** in `KNOWN_EVENTS`, else `"unknown"`. Same for `source` (`KNOWN_SOURCES`).
- `priority`: `float(raw.get("priority", 0.0))`, on `TypeError/ValueError` → `0.0`, then clamp `[0,1]`.
- `context = dict(raw.get("context") or {})`, then `context.setdefault("urgency", "unknown")` —
  **`urgency` is always present**. Copy, so mutating it never affects the request.
- `person` only if `isinstance(..., dict)` else `None`.
- `timestamp`: numeric → `float(...)`; numeric string → `float(str)`; else `time.time()`.
  Unparseable string → `time.time()`.
- `normalize_feedback`: `feedback` default on unknown is **`"ignored"`**; `behavior_id` default
  `"behavior_unknown"`.

## 1.6 `connectome/state_machine.py`
`states: Dict[str, Dict]` — **17 states**, each spec has exactly 10 keys:
`priority`(int), `duration_ms`(int), `animation`(str), `movement`(str), `speed`(float),
`position`(str), `scale`(float), `visibility`(str), `sound`(str|None), `requires_ack`(bool).

| state | prio | dur_ms | animation | movement | speed | position | scale | vis | sound | ack |
|---|---|---|---|---|---|---|---|---|---|---|
| IDLE | 0 | 0 | hover | none | 0.1 | corner | 1.0 | dim | None | False |
| BACKGROUND | 1 | 3000 | drift | slow | 0.2 | corner | 0.8 | low | None | False |
| ATTENTION | 2 | 2500 | perk | toward_center | 0.5 | center_left | 1.2 | normal | None | False |
| CURIOUS | 3 | 3000 | tilt | circle | 0.4 | center | 1.1 | normal | None | False |
| LISTENING | 3 | 4000 | hover_tilt | subtle | 0.3 | bottom_center | 1.1 | normal | None | False |
| THINKING | 4 | 4000 | stutter | minimal | 0.2 | center | 1.0 | normal | None | False |
| TAKEOFF | 4 | 1200 | lift_off | rise | 0.7 | center_upper | 1.2 | normal | None | False |
| FLYING | 5 | 3000 | fly_circle | figure_eight | 0.9 | center | 1.1 | normal | None | False |
| LANDING | 1 | 1200 | swoop | descend | 0.5 | corner_low | 0.9 | dim | None | False |
| PROCESSING | 5 | 3500 | spin | orbiting | 0.6 | center | 1.0 | normal | None | False |
| LEARNING | 6 | 5000 | pulse | slow_orbit | 0.5 | center_upper | 1.2 | bright | None | False |
| IMPORTANT | 7 | 8000 | zoom_alert | toward_user | 0.9 | attention_area | 1.5 | bright | soft_chime | **True** |
| WAITING | 6 | 0 | pacing | sway | 0.3 | bottom_center | 1.0 | normal | None | **True** |
| SUCCESS | 7 | 2500 | happy_bounce | bounce | 0.7 | center | 1.2 | bright | success | False |
| WARNING | 8 | 5000 | shake | agitated | 1.2 | attention_area | 1.3 | bright | chime | False |
| ERROR | 9 | 4000 | falter | stumble | 0.8 | center | 1.0 | normal | error | False |
| SLEEPING | -1 | 0 | slow_pulse | landed | 0.05 | corner | 0.7 | dim | None | False |

`StateMachine(current="IDLE", history=[])`:
- `priority` property → `states[current]["priority"]`
- `allowed_transitions(state)` → `_TRANSITIONS.get(state, DEFAULT_TRANSITIONS[state])`
- `transition_to(next)`: raise `KeyError(f"unknown state {next!r}")` if unknown; if
  `states[next]["priority"] > self.priority` → **always allowed** (escalation bypasses the table);
  elif `next in allowed_transitions(current)` → allowed; else return `None` (no state change, no
  exception). Appends old state to `history` on success.
- `force(state)`: same unknown-state `KeyError`, always succeeds.

`_TRANSITIONS` (16 keys — **IDLE is absent**):
```
SLEEPING:   IDLE, BACKGROUND, ATTENTION, TAKEOFF
BACKGROUND: IDLE, ATTENTION, CURIOUS, SLEEPING, TAKEOFF
ATTENTION:  IDLE, CURIOUS, THINKING, IMPORTANT, LISTENING, SLEEPING, TAKEOFF
CURIOUS:    IDLE, THINKING, LISTENING, IMPORTANT, ATTENTION, TAKEOFF
LISTENING:  IDLE, THINKING, PROCESSING, IMPORTANT, LEARNING, TAKEOFF
THINKING:   IDLE, PROCESSING, IMPORTANT, SUCCESS, WAITING, TAKEOFF
PROCESSING: IDLE, IMPORTANT, SUCCESS, ERROR, WAITING, TAKEOFF
LEARNING:   IDLE, IMPORTANT, SUCCESS, TAKEOFF
IMPORTANT:  IDLE, WARNING, SUCCESS, ERROR, WAITING, FLYING
WAITING:    IDLE, IMPORTANT, WARNING, SUCCESS, FLYING
WARNING:    IDLE, IMPORTANT, ERROR, SUCCESS
SUCCESS:    IDLE, ATTENTION, SLEEPING, FLYING
ERROR:      IDLE, WARNING
TAKEOFF:    FLYING, LANDING, IDLE
FLYING:     LANDING, ATTENTION, IMPORTANT, SUCCESS, IDLE
LANDING:    IDLE, BACKGROUND, SLEEPING, ATTENTION
```
`DEFAULT_TRANSITIONS = {name: set(_TRANSITIONS.keys()) for name in states}`.

## 1.7 `connectome/policy.py` — MOST IMPORTANT FILE
```python
NATURAL_STATE = {          # event -> natural state
  "important_message":"IMPORTANT", "notification":"ATTENTION", "user_message":"LISTENING",
  "task_reminder":"ATTENTION",   "calendar_event":"IMPORTANT",
  "process_completed":"SUCCESS", "process_failed":"ERROR", "warning":"WARNING",
  "app_open":"CURIOUS", "app_idle":"IDLE", "unknown":"IDLE" }

BOOST = 0.35
THRESHOLD = 0.25
FLIGHT_STATES = ("TAKEOFF", "FLYING", "LANDING")          # tuple, exact order
FLIGHT_CELEBRATION = {"SUCCESS", "CURIOUS", "LEARNING"}
FLIGHT_MIN_PRIORITY = 0.3

PATTERNS = {  # state -> {MBON compartment: coefficient}
  "IDLE":{}, "SLEEPING":{},
  "BACKGROUND":{"MBON_gamma":-0.3},
  "ATTENTION":{"MBON_beta":0.4,"MBON_beta2":0.4},
  "CURIOUS":{"MBON_beta2":0.7,"MBON_gamma":0.3},
  "LISTENING":{"MBON_apostrophe":0.6,"MBON_bpost":0.4},
  "THINKING":{"MBON_alpha":0.5,"MBON_beta":0.3},
  "TAKEOFF":{"MBON_beta":0.5,"MBON_output":0.4},
  "FLYING":{"MBON_output":0.8,"MBON_alpha":0.4},
  "LANDING":{"MBON_gamma":0.6,"MBON_bpost":0.4},
  "PROCESSING":{"MBON_beta":0.7},
  "LEARNING":{"MBON_gamma":0.6,"MBON_output":0.5},
  "IMPORTANT":{"MBON_output":0.9,"MBON_alpha":0.5,"MBON_gamma":0.4},
  "WAITING":{"MBON_bpost":0.7,"MBON_output":0.4},
  "SUCCESS":{"MBON_gamma":0.8,"MBON_output":0.5},
  "WARNING":{"MBON_apostrophe":0.8,"MBON_output":0.6},
  "ERROR":{"MBON_output":0.7,"MBON_beta":-0.4},
}

PRIORITY_LEVEL = {  # state -> level string
  "IDLE":"BACKGROUND","BACKGROUND":"BACKGROUND","SLEEPING":"BACKGROUND",
  "ATTENTION":"LOW","CURIOUS":"LOW","LISTENING":"LOW","LANDING":"LOW",
  "THINKING":"MEDIUM","TAKEOFF":"MEDIUM","FLYING":"MEDIUM","PROCESSING":"MEDIUM","LEARNING":"MEDIUM",
  "IMPORTANT":"HIGH","WAITING":"HIGH","SUCCESS":"HIGH",
  "WARNING":"CRITICAL","ERROR":"CRITICAL" }

def score_states(brain) -> Dict[str, float]
def decide(brain, event, force_natural=False, flight=True) -> Dict
```

`score_states` — exact:
```python
mbon = brain.mbon_vector()
for state, coeffs in PATTERNS.items():
    score = sum(c * mbon.get(k, 0.0) for k, c in coeffs.items())
    if coeffs:
        score /= max(1.0, len(coeffs))     # divides only when >= 2 components
    scores[state] = score
```
⇒ `IDLE` and `SLEEPING` always score exactly `0.0`.

`decide` — exact algorithm:
```python
natural = NATURAL_STATE.get(event.name, "IDLE")
scores = score_states(brain)

if force_natural and event.priority > 0.0:
    state = natural
    confidence = max(scores.values(), default=0.0)          # UNBOOSTED max
else:
    candidates = []
    for state, score in scores.items():
        if not flight and state in FLIGHT_STATES:
            continue                       # FILTER flight states out entirely
        candidate = score + (BOOST if state == natural else 0.0)
        candidates.append((candidate, state))
    candidates.sort(reverse=True)          # tuple sort -> ties break by state NAME, reverse-alpha
    top_score, top_state = candidates[0]
    if top_score < THRESHOLD:
        top_state = "IDLE"
    if top_state == "IDLE" and event.priority >= 0.7 and natural != "IDLE":
        top_state = natural
    state = top_state
    confidence = top_score

# celebration-flight override, applied AFTER both branches
if flight and event.priority >= FLIGHT_MIN_PRIORITY and natural in FLIGHT_CELEBRATION:
    state = "FLYING"

return {"state": state,
        "priority": PRIORITY_LEVEL.get(state, "LOW"),
        "confidence": round(confidence, 4),
        "scores": {k: round(v, 4) for k, v in scores.items()},   # ALL 17 states always
        "natural_state": natural}
```

Subtleties that MUST be preserved (each is asserted by a test):
1. `flight=False` removes flight states from the **candidate list only** — they are still present
   in the returned `scores` dict.
2. `confidence` is always `top_score` from the scoring path — it is NOT re-derived after the IDLE
   fallback, the priority rescue, or the FLYING override.
3. The celebration override is unconditional on the scoring path and applies even after
   `force_natural`. It tests the **natural** state, not the winner.
4. `BOOST` (0.35) keeps the natural state above `THRESHOLD` (0.25) even on a cold brain.
5. `PATTERNS` keys must equal `state_machine.states` keys exactly (17 each).

## 1.8 `connectome/reward.py`
```python
REWARD_MAP = {"looked":0.3, "interacted":0.4, "opened_related":0.5, "marked_useful":1.0,
              "reacted_positive":0.8, "ignored":0.0, "dismissed":-0.5,
              "reacted_negative":-0.9, "marked_unnecessary":-1.0}

@dataclass RewardSignal: value: float; feedback_type: str
    @property is_reward  -> value > 0
    @property is_punishment -> value < 0
def map_feedback(feedback_type) -> RewardSignal   # unknown -> 0.0
```

## 1.9 `connectome/store.py` — SQLite persistence
```sql
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, behavior_id TEXT, event TEXT, source TEXT,
  priority REAL, state TEXT, priority_level TEXT, confidence REAL,
  activity_json TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, behavior_id TEXT, feedback TEXT,
  reward_value REAL, created_at REAL);
CREATE TABLE IF NOT EXISTS model_state (
  id INTEGER PRIMARY KEY CHECK (id = 1), weights_json TEXT, updated_at REAL);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions (created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_created  ON feedback  (created_at);
```
`SqliteStore(path=None)` → `path or ":memory:"` (**in-memory default**);
`sqlite3.connect(path, check_same_thread=False)`; every method guarded by a `threading.RLock()`.

API: `close()`, `record_decision(decision: dict, behavior_id)`, `record_feedback(feedback_type,
reward_value, behavior_id)`, `save_weights(weights)`, `load_weights() -> Dict[tuple,float]`,
`decisions(limit=200)`, `feedback_rows()`, `counts() -> {"decisions","feedback"}`,
`latest_weights_json()`.

Quirks to reproduce exactly:
- `record_decision` stores the **final** state from `decision["fetch"]` in the `state` column
  (there is no `"state"` key read). `priority_level` ← `decision["priority_level"]`,
  `confidence` ← `decision["confidence"]`, `activity_json` ← `json.dumps(decision.get("activity", {}))`.
- `save_weights` serializes as `{"KC->MBON_output": w}` and upserts row `id=1`.
  `load_weights` splits on `"->"` back into tuple keys.
- `decisions(limit)` → `ORDER BY id DESC LIMIT {int(limit)}` (f-string, hence the `int()` cast);
  returns keys `behavior_id, event, source, priority, state, priority_level, confidence, created_at`.
- `feedback_rows()` → `ORDER BY id` ascending; keys `behavior_id, feedback, reward_value, created_at`.
- All timestamps `time.time()` at insert time.

## 1.10 `connectome/simulate.py` — CLI + event→circuit encoder
```python
CTX_CHANNELS = 8
def _context_channels(*parts) -> int
def inject_event(brain, event) -> None
def run_brain(brain, event, steps=40) -> Dict
def run_simulation(raw_event, feedback=None, steps=40) -> Dict
```
`inject_event` (the event→circuit encoder, used by server too):
```python
brain.clear_inputs()                      # WIPES pending DAN input
brain.set_input("PN", event.priority)
covered = _context_channels(event.name, event.source, ctx.get("topic",""), ctx.get("urgency",""))
context_drive = 0.15 + 0.6 * (covered / CTX_CHANNELS)
brain.set_input("CTX", min(1.0, context_drive))
```
`_context_channels(*parts)`: for each truthy part take `hashlib.sha256(str(part).encode()).digest()[0] % 8`
into a `set`; return `len(set)`. (sha256's first byte only — stable across runs, unlike `hash()`.)

`run_brain`: `inject_event` → `steps`×`step()` → `decide(brain, event)` (**no `flight=` kwarg**, so
defaults to `True`).

`run_simulation(raw_event, feedback=None, steps=40)` → dict with `event, source, priority` (float),
`brain_state` (full decide dict), `fly_state` (`machine.current` after `transition_to`, which may
differ), `activity` (rounded MBON vector), and when `feedback` is given also
`feedback: {type, reward_value, synapse_delta}` where `synapse_delta` is keyed by **raw tuples**
(only `abs(after-before) > 1e-6` and `graph.nodes[k[0]].type == "kc"`) and the value is the **new
weight** (rounded 4) — note this differs from `server.py`, which returns the actual **difference**
(rounded 5) as `"KC->MBON_x"` strings.

CLI: `--event` (default `important_message`), `--priority` (float, default `0.85`),
`--source` (default `whatsapp`), `--context` (JSON string), `--feedback`, `--steps` (int, 40),
`--json` (stores to `as_json`).

## 1.11 `connectome/influence.py` — Phase-7 production gate (stdlib-only!)
```python
DEFAULT_MODE = os.environ.get("FLY_LEARNED_INFLUENCE", "off").lower()   # read at import time
MODES = ("off", "auto", "on")
CANDIDATE_VERDICT = "CANDIDATE_FOR_PRODUCTION"
REACTION_TO_STATE = {"normal":"IDLE", "face_user":"ATTENTION",
                     "frontflip":"IMPORTANT", "backflip":"WARNING"}
COVERED_CASES = ("text", "image", "audio", "sticker", "video")
EVENT_TO_CASE  = {"user_message":"text", "notification":"image"}   # documentation only, unused
```
`ProductionInfluence(mode=None, snapshot_path=None, evaluation_path=None)`:
- `self.mode = mode.lower() if mode else DEFAULT_MODE`; if not in `MODES` → `"off"`.
- `verdict()` reads `evaluation_path` JSON `.get("verdict")`; on `OSError/ValueError/KeyError/TypeError` → `None`.
- `reactions()` reads `snapshot_path` JSON → `{row["case"]: row["rl_behavior"] for row in data["evaluation"]["rows"]}`;
  any of the same 4 exceptions → `{}`.
- `permitted(verdict)`: `off`→False, `on`→True, `auto`→`verdict == CANDIDATE_VERDICT`.
- `resolve_case(event)`: `user_message`→`"text"`; `notification`→`context["media_type"]` if in
  `COVERED_CASES` else `"image"`; everything else → `None`.
- `apply(event, state) -> (state, status)`: five sequential bail-out gates, each returning the
  **baseline** state with `applied: False`:
  1. not `permitted(verdict)`;
  2. `resolve_case` is `None`;
  3. reaction not in `REACTION_TO_STATE`;
  4. learned state not in `states`, or `learned == state` (no-op);
  5. else apply.
  `status` on bail-out has 5 keys `{mode, verdict, applied:False, from_state, to_state}`;
  on success 9 keys (adds `case`, `reaction`, `source:"rl"`). Callers must use `.get()`.
- `summary()` → `{"mode", "verdict", "permitted", "covered_cases"}`.
- Note: the override changes only the state **string**; `priority_level`/`confidence` stay as the
  baseline computed them. Keep that (tests assert it).

Default paths: `training/rl/experiments/rl_experiment_latest.json` and
`training/evaluation_reports/evaluation_latest.json`. `verdict()`/`reactions()` do file I/O on
**every** request (no caching) — acceptable at this scale.

## 1.12 `connectome/server.py` — stdlib HTTP service
```python
DEFAULT_PORT = 8601
DEFAULT_DB = os.environ.get("FLY_DB", str(Path.home() / ".fly" / "connectome.db"))
```
`FlyBrainService(steps=40, store=None, influence=None, flight=True)`:
- `__init__`: `load_wiring()`, `Brain(graph)`, `store or SqliteStore()`, then
  `self.brain.weights.update(self.store.load_weights())` if any; `self.lock = threading.RLock()`.
- `health()`:
```json
{"status":"ok","service":"fly-python-behavior","graph":<meta.name>,"neurons":<meta.neurons>,
 "decisions":N,"feedback":N,"learned_influence":<influence.summary()>,"flight_mode":"on"|"off"}
```
- `flight_mode()` → `{"flight": bool}`; `set_flight(raw)` → `self.flight = bool(raw.get("flight"))`, returns `{"flight": ...}`.
- `behavior(raw)`: normalize → `inject_event` → `steps`×`step()` → `decide(brain, event, flight=self.flight)`
  → `influence.apply(event, decision["state"])` → result:
```json
{"event":..., "source":..., "priority":..., "context":..., "fetch":<state>,
 "priority_level":..., "confidence":..., "flight":<bool>,
 "activity":{gid: round(a,4)}, "influence":{...}}
```
  then `store.record_decision(result, behavior_id=event.id)` and return it.
  **The response key for the state is `"fetch"`** (not `"state"`) — the Java DTO maps to `fetch`.
- `feedback(raw)`: normalize → `map_feedback` → snapshot `before` → `deliver_reward(value)` →
  **3**×`step()` → `delta` = `{"KC->MBON_x": round(after-before, 5)}` for changed `> 1e-6` where
  `graph.nodes[k[0]].type == "kc"` → `record_feedback` + `save_weights` → returns
  `{"behavior_id","feedback","reward_value","synapse_delta"}`.
- `reset()` → `{"status":"reset"}` (does NOT reset weights).
- `states()` → `{"states":[{"name","priority","priority_level","animation","duration_ms"}, ...]}`.

`Handler(BaseHTTPRequestHandler)`: class-level `routes = {"POST /behavior","POST /feedback",
"POST /reset","POST /mode"}`; `do_GET` handles `/health`, `/states`, `/mode` else
`404 {"error":"not_found"}`; `do_POST` matches `f"POST {self.path}"` **exactly** (query strings are
NOT supported → 404). `_read_json()`: missing/zero `Content-Length` → `b"{}"`; any decode/parse
failure → `{}` (so a malformed body becomes an `unknown` event at priority 0.0, **never a 500**).
All responses `Content-Type: application/json; charset=utf-8`, body
`json.dumps(body, ensure_ascii=False)`. `log_message` overridden to a no-op.

`make_server(port=8601, steps=40, db_path=None, influence=None, flight=True)`.
`main()` (imports argparse locally):
```
--port   int  8601
--steps  int  40
--db     str  DEFAULT_DB
--influence choices("off","auto","on") default=None   # None -> FLY_LEARNED_INFLUENCE or "off"
--flight choices("off","on")       default=None   # None -> FLY_FLIGHT_MODE or "on"
```
`Path(args.db).parent.mkdir(parents=True, exist_ok=True)`; startup line printed with `flush=True`:
`fly-python-behavior listening on 127.0.0.1:{port} (db={db})`; `serve_forever()`;
`KeyboardInterrupt` → `shutdown()`.

**Env vars: `FLY_DB`, `FLY_FLIGHT_MODE` (default "on"), `FLY_LEARNED_INFLUENCE` (default "off").**

## 1.13 `connectome/reference/flywire_live_service.py`
Legacy/unused reference stub (may import flask/caveclient — it is never imported by the engine).

---

# PART 2 — TRAINING / OFFLINE RL / EVALUATION

## 2.1 `training/__init__.py`
Re-exports only `analyze, feedback_distribution, policy_agreement, recent_reward_rate` from `analysis`.

## 2.2 `training/analysis.py`
```python
POSITIVE = {"looked","interacted","opened_related","marked_useful","reacted_positive"}
NEGATIVE = {"dismissed","marked_unnecessary","reacted_negative"}   # defined but unused
def recent_reward_rate(store, window=50) -> Optional[float]   # fraction of last-50 reward_value > 0
def feedback_distribution(store) -> Dict[str,int]
def policy_agreement(store) -> Optional[float]                # None if no joined positive pairs
def analyze(store, window=50) -> Dict[str, Any]
    # {"decisions","feedback_events","reward_rate","policy_agreement","distribution"}
main(): path = sys.argv[1] if len(sys.argv)>1 else None  -> prints analyze() as indented JSON
```

## 2.3 `training/dataset.py` — live DB → labeled dataset
```python
LABEL_POSITIVE="positive"; LABEL_NEGATIVE="negative"; LABEL_NEUTRAL="neutral"; LABEL_UNLABELED="unlabeled"
UNKNOWN = -1
EVENT_CODES          = {name: i for i, name in enumerate(sorted(KNOWN_EVENTS))}
SOURCE_CODES         = {name: i for i, name in enumerate(sorted(KNOWN_SOURCES))}
PRIORITY_LEVEL_CODES = {name: i for i, name in enumerate(sorted(set(PRIORITY_LEVEL.values())))}
STATE_CODES          = {name: i for i, name in enumerate(states)}   # declaration order, NOT sorted
```
Resulting code values (must match `dataset_meta.json`):
```
events:  app_idle 0, app_open 1, calendar_event 2, important_message 3, notification 4,
         process_completed 5, process_failed 6, task_reminder 7, unknown 8, user_message 9, warning 10
sources: app 0, calendar 1, connectors 2, core_brain 3, linkedin 4, tasks 5, unknown 6, whatsapp 7
priority_levels: BACKGROUND 0, CRITICAL 1, HIGH 2, LOW 3, MEDIUM 4
states:  IDLE 0, BACKGROUND 1, ATTENTION 2, CURIOUS 3, LISTENING 4, THINKING 5, TAKEOFF 6,
         FLYING 7, LANDING 8, PROCESSING 9, LEARNING 10, IMPORTANT 11, WAITING 12,
         SUCCESS 13, WARNING 14, ERROR 15, SLEEPING 16
```
`build_dataset(store, limit=None)`:
- `feedback_index` from `store.feedback_rows()`, **latest `created_at` wins** (condition `<=`).
- iterate `store.decisions(limit or 100000)` (newest-first), emit 15 keys in this exact order
  (this is the CSV column order):
```python
{"behavior_id","event","event_code","source","source_code","priority","priority_level",
 "priority_level_code","state","state_code","confidence","reward_value","feedback","label","created_at"}
```
- `label_for(reward)`: `None`→`"unlabeled"`, `>0`→`"positive"`, `<0`→`"negative"`, `0`→`"neutral"`.
- `stats`: `{"decisions","labeled","unlabeled","linkage_rate","positive","negative","neutral",
  "feedback_rows_total"}` where `linkage_rate = round(labeled/decisions*100, 2)`.
- returns `{"records":[...], "stats":{...}, "codes":{"events","sources","priority_levels","states"}}`.

`write_dataset(dataset, out_dir)` → creates dir, writes `train_decisions.csv` (DictWriter,
`newline=""`), `train_decisions.jsonl` (one `json.dumps(record, ensure_ascii=False)` per line),
`dataset_meta.json` (`{"stats","codes"}`, `indent=2`); returns `[csv, jsonl, meta]` **in that order**.

CLI: `--db` (str, None), `--out` (Path, default `connectome/training/datasets`), `--limit` (int, None).
DB resolution: `args.db or os.environ.get("FLY_DB") or ~/.fly/connectome.db`; store closed in `finally`.
stdout:
```
decisions: {n}  labeled: {n} ({rate}%)  +{pos}/-{neg}/0{neutral}
wrote {path}        # × 3
```

## 2.4 `training/rl/rl_brain.py`
```python
try: import torch; import torch.nn as nn
except ImportError: torch = None; nn = None      # so evaluation.py stays importable without torch

BEHAVIORS: Dict[int,str] = {0:"normal", 1:"frontflip", 2:"backflip", 3:"face_user"}

class FlyWireBrainRL(nn.Module if nn is not None else object):
    def __init__(self, in_features=6, hidden=128, out_states=4):
        if nn is None: raise ImportError("torch is required for RL experiments. ...")
        super().__init__()
        self.optic_lobe      = nn.Linear(6, 64)
        self.central_complex = nn.Linear(64, 128)
        self.motor_output    = nn.Linear(128, 2)     # displacement (dx,dy)
        self.behavior_head   = nn.Linear(128, 4)     # behavior logits
        self.relu = nn.ReLU()
    def forward(self, x):   # returns (disp, behav_logits)
        x = self.relu(self.optic_lobe(x))
        h = self.relu(self.central_complex(x))
        return self.motor_output(h), self.behavior_head(h)
# 9542 parameters total; checkpoint is a bare 8-key state_dict

def type_code_of(msg_type) -> float     # image|video -> 1.0 ; ptt|audio -> 2.0 ; sticker -> 3.0 ; else 0.0
def baseline_behavior(type_code) -> int
    # 1.0 -> 1 (frontflip) ; 3.0 -> 2 (backflip) ; else -> 3 (face_user)
def sample_goal_for_type(type_code, text_len, cur_x, cur_y) -> (gx, gy)
    # radius = 0.45 if type_code==1.0 else (0.30 if ==2.0 else 0.15)
    # angle  = type_code*1.7 + text_len*0.05 + 1.3
    # clamp gx,gy to [0.02, 0.98]
```

## 2.5 `training/rl/offline_exp.py`
```python
MESSAGE_CASES = [("text",0.0,baseline_behavior(0.0)), ("image",1.0,baseline_behavior(1.0)),
                 ("audio",2.0,baseline_behavior(2.0)), ("sticker",3.0,baseline_behavior(3.0)),
                 ("video",1.0,baseline_behavior(1.0))]
MODEL_DIR     = Path(__file__).parent / "experiments"
DEFAULT_MODEL = MODEL_DIR / "brain_model.pt"
```
`evaluate(model, cases=MESSAGE_CASES)` — duck-typed seam: `model` only needs
`predict_behavior(type_code, text_len, cur_x, cur_y, goal_x, goal_y) -> int`, so it is unit-testable
**without torch**. Per case: `cur=(0.5,0.5)`, `goal=sample_goal_for_type(type_code, 12, 0.5, 0.5)`
(`text_len` hard-coded `12`). Returns
`{"evaluated_cases","agreed_cases","policy_agreement","rows":[{"case","rl_behavior","baseline_behavior","agree"}]}`.

`warm_up(episodes=4000, model_path=DEFAULT_MODEL)` — imports `torch` and `F` **inside** the function:
- `Adam(params, lr=1e-2)`; if `model_path.exists()` load the checkpoint and print
  `Resumed from existing checkpoint {path}`.
- per episode: `type_code = random.choice([0.0,0.0,1.0,2.0,3.0])` (**text double-weighted**),
  `text_len = random.uniform(1,300)`, `cur = (random(), random())`,
  `goal = sample_goal_for_type(type_code, int(text_len), cur[0], cur[1])`.
- input `[type_code, text_len/500.0, cur_x, cur_y, goal_x, goal_y]`;
  `target_disp = [clamp(goal-cur, -1, 1)]`;
  `target_behav = torch.LongTensor([baseline_behavior(type_code)])`.
- `loss = F.mse_loss(disp, target_disp) + 0.5*F.cross_entropy(behav_logits, target_behav)`.
- log `losses.append((ep, round(float(loss),4)))` every 400 episodes; then `mkdir`, `.eval()`,
  `torch.save(state_dict, model_path)`.
- returns `{"episodes","duration_s","checkpoint","loss_curve"}`.

`TorchModel(model_path=DEFAULT_MODEL, train_steps=800)` loads the checkpoint if present, `.eval()`,
`predict_behavior(...)` runs under `torch.no_grad()` and returns `int(argmax(...))`.
(`self.sanity = train_steps` is vestigial.)

CLI: `--episodes` (4000), `--model` (Path), `--json`. Order: `warm_up` → `TorchModel` → `evaluate`
→ write `experiments/rl_experiment_latest.json` = `{"train":{...},"evaluation":{...}}`.
**This module never reads the dataset** — warm-up is fully synthetic.

## 2.6 `training/evaluation.py` — the Phase-6/7 gate
```python
SCENARIOS = {
 "text":    {"event":"user_message",   "priority":0.40,
             "prior":{"reacted_positive":0.30,"looked":0.25,"ignored":0.35,"dismissed":0.10}},
 "image":   {"event":"notification",   "priority":0.75,
             "prior":{"reacted_positive":0.45,"looked":0.30,"ignored":0.15,"dismissed":0.10}},
 "audio":   {"event":"notification",   "priority":0.85,
             "prior":{"marked_useful":0.40,"reacted_positive":0.25,"looked":0.20,"ignored":0.10,"dismissed":0.05}},
 "sticker": {"event":"notification",   "priority":0.60,
             "prior":{"reacted_positive":0.35,"looked":0.30,"ignored":0.25,"dismissed":0.10}},
 "video":   {"event":"notification",   "priority":0.75,
             "prior":{"reacted_positive":0.45,"looked":0.30,"ignored":0.15,"dismissed":0.10}},
}   # all priors sum to exactly 1.0

ENGAGED = frozenset({"face_user","frontflip","backflip"})
NORMAL  = "normal"
STATE_REACTION = {  # covers all 17 states
 "IDLE":NORMAL,"BACKGROUND":NORMAL,"SLEEPING":NORMAL,"THINKING":NORMAL,"PROCESSING":NORMAL,
 "LEARNING":NORMAL,"LANDING":NORMAL,
 "TAKEOFF":"face_user","FLYING":"face_user","LISTENING":"face_user","ATTENTION":"face_user",
 "CURIOUS":"face_user",
 "IMPORTANT":"frontflip","WAITING":"frontflip","SUCCESS":"frontflip",
 "WARNING":"backflip","ERROR":"backflip"}
REPORT_DIR       = Path(__file__).parent / "evaluation_reports"
DEFAULT_SNAPSHOT = Path(__file__).parent / "rl" / "experiments" / "rl_experiment_latest.json"
```
Reward math (pure, unit-tested):
```python
expected_reward(t)  = round(sum(p*REWARD_MAP[k] for k,p in SCENARIOS[t]["prior"].items()), 4)
penalized_reward(t) = round(positive_mass*REWARD_MAP["dismissed"] + dismiss_mass*REWARD_MAP["ignored"], 4)
                     # positive_mass = sum(p where REWARD_MAP[k] > 0); dismiss_mass = rest (incl. ignored 0.0)
graded_reward(t, r) = expected_reward(t) if r in ENGAGED else penalized_reward(t)
```
Computed: text `0.265/-0.275`, image `0.400/-0.375`, audio `0.635/-0.425`, sticker `0.320/-0.325`,
video `0.400/-0.375`.

`baseline_reactions(events=None)` — **the real brain is the baseline**:
```python
graph = load_wiring()
for name, spec in SCENARIOS.items():
    brain  = Brain(graph)                      # fresh brain per case
    event  = Event(id=f"eval_{name}", name=spec["event"], source="whatsapp",
                   priority=spec["priority"], person=None,
                   context={"urgency": "high" if spec["priority"] >= 0.7 else "medium"},
                   timestamp=0.0)
    inject_event(brain, event)
    for _ in range(40): brain.step()
    reactions[name] = STATE_REACTION.get(decide(brain, event)["state"], NORMAL)
```
`Event` is imported lazily inside the function. The `events` parameter is accepted and ignored.
**Actual output (verified): all five cases → `face_user`**, because
`user_message→LISTENING` and `notification→ATTENTION`, and both map to `face_user`.

`load_rl_reactions(snapshot)`: raise `FileNotFoundError` if missing; else
`{row["case"]: row["rl_behavior"] for row in data["evaluation"]["rows"]}`.

`evaluate(baseline, learned, cases=None)`:
- missing case in either map → `NORMAL`;
- per row: `agree = base == rl`; `reward_delta = round(graded_reward(rl) - graded_reward(base), 4)`;
- `policy_agreement = round(agreed/total, 4)`; `mean_reward_delta_vs_baseline`; `degraded_cases = any(delta < 0)`.
- **Verdict ladder (exact order):**
  1. `agreed >= total` → `"CANDIDATE_FOR_PRODUCTION"`, `safe_to_influence_production = True`
  2. elif `degraded` → `"KEEP_BASELINE"`, `False`
  3. else → `"COLLECT_MORE_DATA"`, `False`
- result keys: `compared_cases, policy_agreement, mean_reward_delta_vs_baseline, degraded_cases,
  verdict, safe_to_influence_production, rows`; row keys: `case, priority, baseline_reaction,
  rl_reaction, agree, reward_baseline, reward_rl, reward_delta`.

CLI `--snapshot` (Path), `--json`; always writes `evaluation_reports/evaluation_latest.json`
(`indent=2, ensure_ascii=False`).

## 2.7 Generated artifacts (git-ignored, must be produced by running the CLIs)
`dataset_meta.json` at the current state of the reference project:
```json
{"stats":{"decisions":127,"labeled":97,"unlabeled":30,"linkage_rate":76.38,
          "positive":76,"negative":8,"neutral":13,"feedback_rows_total":114}, "codes":{...}}
```
`rl_experiment_latest.json`: `train` = 4000 episodes / ~3.4 s, `loss_curve` every 400 eps;
`evaluation.policy_agreement` 0.8, rows: text face_user ✓, image frontflip ✓, audio backflip ✗,
sticker backflip ✓, video frontflip ✓ (measured against **Baseline A**, see §8.1).
`evaluation_latest.json`: `policy_agreement` 0.2, `mean_reward_delta` 0.0, `degraded_cases` false,
`verdict` **`COLLECT_MORE_DATA`**, `safe_to_influence_production` **false** (measured against
**Baseline B**, the real brain).

---

# PART 3 — SPRING BOOT BACKEND

`backend/pom.xml`: parent `spring-boot-starter-parent:3.3.5`, `groupId com.fly`,
`artifactId connectome-backend`, `version 0.1.0`, **`java.version` 21**; dependencies
`spring-boot-starter-web`, `-validation`, `-websocket` (raw Spring WebSocket, **not** STOMP),
`spring-boot-starter-test`; plugin `spring-boot-maven-plugin`. **No Lombok, no Spring Security,
no JPA, no actuator.**

`application.yml` (exact):
```yaml
server:
  port: 8080
app:
  python:
    base-url: ${FLY_PYTHON_URL:http://127.0.0.1:8601}
    connect-timeout: 2s
    read-timeout: 4s
    max-attempts: ${FLY_PYTHON_MAX_ATTEMPTS:2}
  developer:
    enabled: ${FLY_DEVELOPER_MODE:false}
    bubble-ms: ${FLY_DEVELOPER_BUBBLE_MS:7000}
  security:
    api-token: ${FLY_API_TOKEN:}
logging:
  level:
    com.fly.connectome: DEBUG
```
**There is no HTTP CORS config** (only the WebSocket origin is `*`).

`FlyApplication`: `@SpringBootApplication @ConfigurationPropertiesScan`.

`PythonProperties`: `@ConfigurationProperties(prefix="app.python")` record
`(String baseUrl, Duration connectTimeout, Duration readTimeout, int maxAttempts)`.

### 3.1 Endpoints (13 total)
`FlyController` (`@RestController @RequestMapping("/api/v1")`, deps
`EventNormalizationService, BehaviorGateway, FlyBroadcaster`):

| # | Method | Path | Notes |
|---|---|---|---|
|1|POST|`/api/v1/events`|`@Valid EventRequest` → `gateway.decide(...).withBehaviorId(event.id())` → broadcast → 200 `BehaviorDecision`|
|2|POST|`/api/v1/feedback`|`@Valid FeedbackRequest` → `gateway.applyFeedback` → broadcast `{"type":"fly_feedback_result","result":...}` → 200 `Map`|
|3|GET|`/api/v1/health`|→ `HealthResponse.up("UP", python)` if `python.reachable == true` else `degraded("DOWN", python)`. **Always HTTP 200**|
|4|GET|`/api/v1/states`|→ `gateway.states()`|
|5|GET|`/api/v1/mode/flight`|→ `gateway.flightMode()` (Python `GET /mode`)|
|6|POST|`/api/v1/mode/flight`|body `{"flight":bool}` → `gateway.setFlight(Boolean.TRUE.equals(body.get("flight")))`. **Not** `@Valid`|
|7|GET|`/api/v1/events/contract`|static contract doc: `{"direction":"core_brain/connectors -> connectome -> behavior engine","version":"v1","example":{event:"important_message", source:"whatsapp", priority:0.85, person:{id:"person_123"}, context:{topic:"job",urgency:"high"}, timestamp:"2026-09-24T13:00:00Z"}}`|

Broadcast for #1 (and the WhatsApp webhook): `Map.of("type","fly_behavior","behavior_id",event.id(),
"decision",decision,"context",event.context())` — the WS `behavior_id` is **always** exactly the
`event.id()` sent to Python (this is the join key for the learning dataset; there is a regression
test for it).

`DeveloperController` (`@RequestMapping("/api/v1/developer")`, deps `DeveloperModeService,
DeveloperEventMapper, FlyBroadcaster`): `POST /developer/events` (`@Valid`), `GET /developer/mode`,
`POST /developer/mode` (`@RequestBody DeveloperModeRequest`), `GET /developer/contract`.
`POST /developer/events` is a 3-stage gate where **every path returns HTTP 200**:
1. mode off → `{"status":"ignored","reason":"developer_mode_off","type":...}` (no broadcast);
2. unsupported type → `{"status":"ignored","reason":"event_type_not_implemented"|"unsupported_event_type","type":...}`;
3. processed → broadcast `{"type":"developer_event","behavior_id","decision","context":{"developer":{...}}}`
   and respond `{"status":"processed","decision":...,"developer":<context.developer>}`.
`GET /developer/contract` returns `direction:"core_brain -> connectome -> fly"`,
`supported:["developer.bug_detected"]`,
`reserved:["developer.explanation","developer.fix_proposed","developer.test_result","developer.review_finding","developer.deploy_status"]`,
`severities:["info","warning","error"]`, `version:"v1"`, plus an `example` payload.

`WhatsAppWebhookController` (`@RequestMapping("/api/v1/whatsapp")`):
`POST /whatsapp/webhook` (`@Valid WhatsAppMessageRequest`) → `mapper.map` → decide → broadcast;
`GET /whatsapp/webhook` → `{"status":"active","endpoint":"POST /api/v1/whatsapp/webhook","note":"accepts {sender, senderName, body, type, timestamp}"}`.

### 3.2 Security (`ApiSecurityConfig` + `ApiTokenInterceptor`)
`ApiSecurityConfig implements WebMvcConfigurer`, constructor `@Value("${app.security.api-token:}")`
→ registers the interceptor on exactly these 5 paths:
```
/api/v1/events, /api/v1/feedback, /api/v1/whatsapp/webhook,
/api/v1/developer/events, /api/v1/developer/mode
```
`ApiTokenInterceptor.preHandle`:
```java
if (token.isEmpty()) return true;                                 // auth disabled
if (!"POST".equalsIgnoreCase(request.getMethod())) return true;   // reads never challenged
if (token.equals(request.getHeader("X-Fly-Token"))) return true;
response.setStatus(401); response.setContentType("application/json");
response.getWriter().write("{\"code\":\"unauthorized\"}"); return false;
```
Configured token is `trim()`ed; the supplied header is NOT trimmed; comparison is case-sensitive
`String.equals`. `POST /api/v1/mode/flight` is deliberately **not** in the list (remains open).

### 3.3 Gateway layer
`BehaviorGateway` (`@Component`; ctor `PythonProperties, ObjectMapper, FallbackPolicy`) builds a
`RestClient` with `SimpleClientHttpRequestFactory(connectTimeout, readTimeout)`. Helper
`text(JsonNode, field) = node.path(field).asText("unknown")` — **missing JSON fields silently
become `"unknown"`**.
- `decide(Normalized)`: POST `/behavior` with `LinkedHashMap` body
  `{id, event, source, priority, context, person}`; if the reply has a non-null `"error"` key →
  `IllegalStateException`. Field mapping: `behaviorId = null` (filled by
  `.withBehaviorId(event.id())` upstream), `event`, `source`, `priority` (`asDouble(request
  priority)`), **`fetch` ← `"fetch"`**, `priorityLevel` ← `"priority_level"`,
  `confidence` (`asDouble(0.0)`), `activity` (empty map if missing), `fallback=false`.
  Wrapped in `Retryer.attempt(..., maxAttempts)`. **On any exception** →
  `log.warn(...)` + `fallback.decide(event, exc.getClass().getSimpleName())`.
- `applyFeedback(FeedbackRequest)`: POST `/feedback` with `{behavior_id, feedback}`; retried;
  returns the whole JSON as a `Map`; on failure returns
  `Map.of("error","python_unavailable","detail",<ExceptionSimpleName>)`.
- `health()`: GET `/health`; adds `details.put("reachable", true)`; on `ResourceAccessException`
  or any other `Exception` → `log.info` + `fallback.pythonDownHealth()`.
- `states()`: GET `/states`; guard `node.path("states").isMissingNode()` → throw; success returns
  `Map.of("source","python","states",<list>)`; failure returns
  `Map.of("source","fallback","states",List.of(),"error",<SimpleName>)`.
- `flightMode()`: GET `/mode`; failure → `Map.of("flight", true, "reachable", false)`
  (**fail-safe: Fly falls back to being able to fly rather than mute**).
- `setFlight(boolean)`: POST `/mode` with `{"flight":enabled}`; **not retried**; failure should
  return `flight: null, error: "python_unavailable", detail: <SimpleName>` — use a null-tolerant map
  (`Map.of` rejects null values; the original code has this latent bug — reproduce the *intent*,
  fix the crash).
- `decide`/`applyFeedback` are retried; `health`/`states`/`flightMode`/`setFlight` are not.

`Retryer` (final class, static):
```java
@FunctionalInterface public interface Body<T> { T run() throws Exception; }
public static <T> T attempt(Body<T> body, int attempts) throws Exception {
    int n = Math.max(1, attempts); Exception last = null;
    for (int i = 0; i < n; i++) {
        try { return body.run(); }
        catch (Exception exc) { last = exc; if (i < n-1) Thread.sleep(backoffMillis(i)); }
    }
    if (last == null) throw new IllegalStateException("no attempts configured");
    throw last;
}
static long backoffMillis(int attempt) { return 50L * (attempt + 1); }   // 50ms, 100ms, 150ms
```

`FallbackPolicy` (`@Component`, stateless):
- `decide(Normalized, String reason)` — the `reason` argument is accepted and unused.
  event → state: `important_message|calendar_event`→`IMPORTANT`, `warning`→`WARNING`,
  `process_failed`→`ERROR`, `process_completed`→`SUCCESS`, `user_message`→`LISTENING`,
  `task_reminder|notification`→`ATTENTION`, `app_open`→`CURIOUS`, `app_open`…,
  `app_idle`→`IDLE`, default `priority >= 0.7 ? "IMPORTANT" : "IDLE"`.
  state → level: `WARNING|ERROR`→`CRITICAL`, `IMPORTANT|WAITING|SUCCESS`→`HIGH`,
  `THINKING|PROCESSING|LEARNING`→`MEDIUM`, `ATTENTION|CURIOUS|LISTENING`→`LOW`, default
  `BACKGROUND`. Returns `BehaviorDecision.fallback(event, fetch, level)`.
- `pythonDownHealth()` → `Map.of("status","DOWN","reason","behavior engine unreachable;
  rule-based fallback active")` — **deliberately has no `reachable` key**, which is the sentinel
  `FlyController.health()` checks with `Boolean.TRUE.equals(...)`.

### 3.4 DTOs (all Java `record`s)
`ApiError(code, message, details:Map, timestamp)` + `static of(...)` stamping
`Instant.now().toString()`.
`BehaviorDecision(behaviorId, event, source, double priority, fetch, priorityLevel, double
confidence, Map<String,Double> activity, boolean fallback)` + `static fallback(event, fetch, level)`
and `withBehaviorId(String)` (only sets when arg non-null AND current is null — idempotent).
`DeveloperEventRequest(@NotBlank type, eventId, @NotBlank repository, @NotBlank file, Integer line,
Integer column, title, @NotBlank message, @NotBlank severity)`.
`DeveloperModeRequest(boolean enabled)`.
`EventRequest(id, @NotNull @DecimalMin("0.0") @DecimalMax("1.0") Double priority, @NotBlank event,
@NotBlank source, context, person, timestamp)` + nested
`EventRequest.Normalized(id, name, source, double priority, context, person)`.
`FeedbackRequest(@NotBlank behaviorId, @NotBlank feedback)`.
`HealthResponse(status, python, components)` + `static up(...)` → `("UP", ...)` with
`components = Map.of("python", details)` and `static degraded(...)` → `("DEGRADED", ...)`.
`WhatsAppMessageRequest(sender, senderName, body, @NotBlank type, @NotNull Long timestamp)`.
`ApiExceptionHandler` (`@RestControllerAdvice`): `MethodArgumentNotValidException` → 400
`{"code":"validation_failed","message":"invalid request payload","details":{field:msg},...}`;
any other `Exception` → 500 `{"code":"internal_error","message":exc.getMessage(),"details":{}}`.
(There is **no** `HttpMessageNotReadableException` handler — malformed JSON yields 500. Keep, or
improve deliberately; either way keep it documented.)

### 3.5 WebSocket
`WebSocketConfig` (`@Configuration @EnableWebSocket`) registers `FlyBroadcaster` at path
**`/ws/fly`** with `.setAllowedOrigins("*")`. Raw Spring WebSocket, no STOMP, no inbound handling
(`handleTextMessage` not overridden — client→server messages are ignored).

`FlyBroadcaster extends TextWebSocketHandler` (`@Component`): `Set<WebSocketSession>` backed by
`ConcurrentHashMap.newKeySet()`; `afterConnectionEstablished/Closed` add/remove + `log.debug`;
`clientCount()`; `broadcast(Object payload)` → `mapper.writeValueAsString`, then for every open
session `sendMessage(new TextMessage(json))`, on failure `log.warn` + `close(SERVER_ERROR)`
(removing the session if closing also throws). Serialization failure is swallowed with a warning.

### 3.6 Services
`EventNormalizationService` (`@Service`) — `KNOWN_EVENTS`/`KNOWN_SOURCES` as `Set.of(...)` matching
the Python vocabularies. `normalize(request)`: unknown name/source → `"unknown"`; priority clamped
`[0,1]`; `context = new HashMap<>(...)` + `putIfAbsent("urgency","unknown")` + `Map.copyOf`;
`id = request.id() == null ? UUID.randomUUID().toString() : request.id()`; `person` passed through
(may be null); **the request `timestamp` is discarded** (`Normalized` has no timestamp).

`WhatsAppEventMapper` (`@Service`, `SOURCE="whatsapp"`, `BODY_PREVIEW=80`) — package-private
statics are unit-tested directly:
- `normalizeType`: `null`→`"chat"`; else lowercase (`Locale.ROOT`) then
  `ptt|audio|voice`→`audio`, `image|photo`→`image`, `video|gif`→`video`, `sticker`→`sticker`,
  default→`"text"`.
- `eventName`: `audio|image|video|sticker`→`"notification"`, default→`"user_message"`.
- `priority`: audio `0.85`; image/video `0.75`; sticker `0.6`; default `0.4`.
- `context`: `LinkedHashMap` with `sender` (or `"unknown"`), `sender_name` (or `"unknown"`),
  `media_type` (normalized), `body_preview` → `Map.copyOf`.
- `preview`: `null`→`""`; `replaceAll("\\s+"," ").trim()`; if `length <= 80` return as-is else
  `substring(0,80) + "\u2026"` (so a truncated preview is 81 chars).
- `map()`: id is **always** a fresh UUID; `person` is always `null`.

`DeveloperLocationMapper` — `CODE_ANCHORS = List.of("code_1","code_2","code_3","code_4")`,
`FALLBACK_ANCHOR = "attention_area"`, nested `record Location(String anchor, boolean mapped)`;
`map(repository, file, line)`: blank repo or file → `Location(FALLBACK_ANCHOR, false)`; else
`slot = Math.floorMod(Objects.hash(repository, file), 4)` → `Location(CODE_ANCHORS.get(slot), true)`.
Deterministic and **ignores `line`**.

`DeveloperEventMapper` — ctor `(DeveloperLocationMapper, @Value("${app.developer.bubble-ms:7000}")
long bubbleMs)`; constants `BUG_DETECTED="developer.bug_detected"`,
`SUPPORTED_TYPES={BUG_DETECTED}`,
`RESERVED_TYPES={developer.explanation, developer.fix_proposed, developer.test_result,
developer.review_finding, developer.deploy_status}`, `KNOWN_SEVERITIES={info,warning,error}`.
Severity matrix:
| severity | state | level | priority | confidence |
|---|---|---|---|---|
| error | `ERROR` | `CRITICAL` | 0.95 | 1.0 |
| warning | `WARNING` | `HIGH` | 0.75 | 1.0 |
| info/unknown | `ATTENTION` | `LOW` | 0.5 | 1.0 |
`toDecision`: id = `eventId` if non-blank else fresh UUID; `event = request.type()`;
`source = "core_brain"`; `activity = Map.of()`; `fallback = false`. **Developer events bypass
`BehaviorGateway` entirely** (no Python call, no retry, no fallback).
`contextFor` builds a `LinkedHashMap` `developer` with keys `type, event_id, repository, file, line,
column, title, message, severity, anchor, mapped, bubble_ms` and returns
`Map.of("developer", developer)`. `titleFor` falls back to `request.type()` when title is blank.

`DeveloperModeService` — `AtomicBoolean` seeded from
`@Value("${app.developer.enabled:false}")`; `isEnabled()`, `setEnabled(v)` returns the new value.
In-memory only (resets on restart).

---

# PART 4 — DESKTOP (Electron + Three.js)

`desktop/package.json`: `{"name":"fly-desktop","version":"0.1.0","main":"src/main.js","type":"module",
"scripts":{"start":"electron .","test":"node --test test/"},
"dependencies":{"three":"^0.169.0"},"devDependencies":{"electron":"^33.0.2"}}`.

`src/index.html`: ESM entry `<script type="module" src="./renderer.js">`; CSP
`default-src 'self'; connect-src 'self' ws://127.0.0.1:8080 http://127.0.0.1:8080;
style-src 'self' 'unsafe-inline'`; dark CSS vars `--bg:#0b0f14 --panel:rgba(18,24,32,0.82)
--line:#24303c --text:#d7e0e8 --muted:#7f8fa3 --accent:#4aa3ff --ok:#2ecc71 --warn:#e67e22
--bad:#e74c3c`; `body{margin:0;overflow:hidden}`.
Element IDs (exact): `speech-bubble` (with `::after` caret, `transform: translate(-50%,-100%)`,
`max-width:340px`, `z-index:20`, `display:none` by default) containing
`span.speaker / span.text / span.meta`; `toast` (bottom-center, `.visible` class, children
`.t-k`/`.t-r`); `hud` with `.row` → `ws-dot` + `state`, plus `hud-tag`; `panel` (right, width
`300px`) containing `event-picker` (select), `priority` (range 0..1 step 0.05 value 0.5),
`priority-value`, `topic` (text, value `job`), `msg` (text, placeholder
`məs. İş təklifi gəldi: Senior Engineer`), `send` (button), `demo-cycle` (button), 6
`[data-feedback]` buttons (`looked, marked_useful, dismissed, marked_unnecessary, interacted,
ignored`), `dev-mode` (checkbox, label "Receive Core Brain developer events"), **`flight-mode`**
(checkbox, label `Fly uça bilər (off: oturur + eventə reaksiya)`).

`src/main.js`: `BrowserWindow({width:960,height:680,title:"Fly / Connectome",backgroundColor:"#0b0f14",
webPreferences:{preload,contextIsolation:true,nodeIntegration:false}})`, `loadFile(index.html)`;
`FLY_OPEN_DEVTOOLS==="1"` → `openDevTools()`; `FLY_SMOKE==="1"` → pipe renderer console as
`[renderer:<level>] <msg>`, and on `did-finish-load` after 2000 ms print **`FLY_SMOKE_OK`** and
`app.exit(0)`; `render-process-gone` → `FLY_SMOKE_CRASH <reason>` + `exit(1)`.

`src/preload.cjs`: `contextBridge.exposeInMainWorld("flyApi", {platform, versions:{electron, chrome}})`.
No IPC; the renderer talks to the backend over WebSocket + `fetch`.

`src/animations.js` (exported: `POSITIONS, STATE_SPEC, resolve, positionOf, defaultDispatcherTimeMs`):
```js
POSITIONS = {
  corner:[-3.2,1.4,-2.0], corner_low:[-3.2,0.5,-2.0], center:[0,0,0],
  center_left:[-0.9,0.3,0], center_upper:[0,1.0,0], bottom_center:[0,-1.6,0],
  attention_area:[0,0.3,1.6],
  code_1:[-2.4,0.6,0.4], code_2:[-0.8,1.2,0.8], code_3:[0.8,0.4,0.6], code_4:[2.4,1.0,0.2] }
```
`STATE_SPEC` (note: these are the **renderer**'s values and deliberately differ from the Python
`state_machine` where the visual layer was tuned):
| state | animation | movement | speed | position | scale | visibility | duration_ms | priority | extras |
|---|---|---|---|---|---|---|---|---|---|
| IDLE | perch | landed | 0.05 | corner_low | 0.7 | dim | 0 | 0 | |
| BACKGROUND | drift | slow | 0.2 | corner | 0.8 | low | 3000 | 1 | |
| ATTENTION | perk | toward_center | 0.5 | center_left | 1.2 | normal | 2500 | 2 | |
| CURIOUS | tilt | circle | 0.4 | center | 1.1 | normal | 3000 | 3 | |
| LISTENING | hover_tilt | subtle | 0.3 | bottom_center | 1.1 | normal | 4000 | 3 | |
| THINKING | stutter | minimal | 0.2 | center | 1.0 | normal | 4000 | 4 | |
| TAKEOFF | lift_off | rise | 0.7 | center_upper | 1.2 | normal | 1200 | 4 | |
| FLYING | fly_circle | figure_eight | 0.9 | center_upper | 1.15 | bright | 3000 | 5 | |
| LANDING | swoop | descend | 0.5 | corner_low | 0.9 | dim | 1200 | 1 | |
| PROCESSING | spin | orbiting | 0.6 | center | 1.0 | normal | 3500 | 5 | |
| LEARNING | pulse | slow_orbit | 0.5 | center_upper | 1.2 | bright | 5000 | 6 | |
| IMPORTANT | zoom_alert | toward_user | 0.9 | attention_area | 1.5 | bright | 8000 | 7 | `requires_ack:true`, `sound:"soft_chime"` |
| WAITING | pacing | sway | 0.3 | bottom_center | 1.0 | normal | 0 | 6 | `requires_ack:true` |
| SUCCESS | happy_bounce | bounce | 0.7 | center | 1.2 | bright | 2500 | 7 | `sound:"success"` |
| WARNING | shake | agitated | 1.2 | attention_area | 1.3 | bright | 5000 | 8 | `sound:"chime"` |
| ERROR | falter | stumble | 0.8 | center | 1.0 | normal | 4000 | 9 | `sound:"error"` |
| SLEEPING | slow_pulse | landed | 0.05 | corner_low | 0.7 | dim | 0 | -1 | |
`resolve(state)` → `STATE_SPEC[state] ?? {...STATE_SPEC.IDLE, fallback:true}`;
`positionOf(pos)` → `POSITIONS[pos] ?? POSITIONS.corner`.

`src/sound.js` — WebAudio synth, **no audio files**:
```js
SOUND_SPECS = {
  soft_chime: [{f:523.25,t:0.00,dur:0.24},{f:659.25,t:0.18,dur:0.24},{f:783.99,t:0.36,dur:0.30}], // C5 E5 G5
  chime:      [{f:659.25,t:0.00,dur:0.18},{f:880.00,t:0.20,dur:0.26}],                             // E5 A5
  success:    [{f:523.25,t:0.00,dur:0.12},{f:659.25,t:0.10,dur:0.12},{f:1046.50,t:0.20,dur:0.30}],  // C5 E5 C6
  error:      [{f:174.61,t:0.00,type:"sawtooth",dur:0.28},{f:130.81,t:0.06,type:"sawtooth",dur:0.30}] // F3 C3
}
```
`describeSound(name)` → preset array or `null`; `unlockAudio()` gated on first user interaction
(bound to `pointerdown`/`keydown`, listeners removed after first fire); gain envelope
`0.0001 → 0.12 (at +0.02) → 0.0001 (at +dur)`, `osc.stop(start+dur+0.05)`, resume the context if
suspended.

`src/developer.js`:
```js
export const DEFAULT_BUBBLE_MS = 7000;
resolveDeveloperBubble(context) -> {speaker: `${SEVERITY} · ${title}`, text: dev.message (verbatim),
                                    meta: "repository / file:line:column", durationMs}
anchorFor(context) -> dev.anchor (string) or null
```
`meta` = `[repository, file].join(" / ")` + `:line` (+`:column` when finite); `title` falls back to
`dev.type`; severity uppercased and lowercased-input-tolerant; `durationMs` from `dev.bubble_ms`
when finite else `DEFAULT_BUBBLE_MS`. `resolveDeveloperBubble(null)`/`({})` → `null`.

`src/renderer.js` — the big one:
```js
import * as THREE from "../node_modules/three/build/three.module.js";   // relative path, not a bare specifier
import { resolve, positionOf } from "./animations.js";
import { resolveDeveloperBubble, anchorFor } from "./developer.js";
import { playStateSound, unlockAudio } from "./sound.js";
const WS_URL = "ws://127.0.0.1:8080/ws/fly";
const API_URL = "http://127.0.0.1:8080/api/v1";
```
Scene: `background 0x0b0f14`; `PerspectiveCamera(55, aspect, 0.1, 100)` at **`(0, 1.5, 7.0)`**,
`lookAt(0,0,0)`; `WebGLRenderer({antialias:true})`, `setPixelRatio(min(dpr,2))`;
`AmbientLight(0xffffff,0.7)`, `DirectionalLight(0xffffff,1.2)` at `(3,6,4)`,
`DirectionalLight(0x88ccff,0.6)` at `(-4,1,-3)`; floor `CircleGeometry(4.2,48)` color `0x141a21`
at `y=-1.4` rotated `-PI/2`; `GridHelper(9,18,0x222a33,0x181f27)` at `y=-1.38`.

`buildFly(texture)`:
- **billboard branch** (when `models/fly.png` loaded): `const FLY_TEXTURE_URL = "../models/fly.png"`;
  `height = 0.62`; `width = height * clamp(aspect, 0.5, 2.2)`;
  `MeshStandardMaterial({map, transparent:true, depthWrite:false, side:THREE.DoubleSide})`;
  `PlaneGeometry(width, height)`; `userData = {materials:[mat], billboard:true}`.
- **primitive branch** (`buildFly(null)`): body sphere `0.16` scale `(1,0.8,1.6)` color `0x2a2f35`;
  thorax `0.12` at `(0,0.02,-0.32)`; head `0.1` at `(0,0.01,-0.5)`; eyes `0.045` at `(±0.07,0.05,-0.46)`
  color `0x661122`; wings from two `absellipse(1.4,0,0.95,0.5,...)` halves scaled `0.16`,
  `wingRoot` at `(0,0.04,-0.22)`, `wingL` at `(0.55,0.05,0)` `rotation.y=-0.35`,
  `wingR` at `(-0.55,0.05,0)` `rotation.y=PI+0.35`, wing material color `0x9fd8ff` `opacity 0.55`;
  3 leg pairs at `z = 0.15 - i*0.22`; antennae at `(±0.035,0.1,-0.52)` `rotation.x=-0.5`.
- Texture load via `TextureLoader().load(FLY_TEXTURE_URL, onLoad, undefined, onError)`; on success
  `texture.colorSpace = THREE.SRGBColorSpace`, build the billboard fly, copy
  `position`/`visible` from the old one, swap it in; on error
  `console.warn("no fly image at ... , keeping primitive fly")`.

`runtime` object (exact shape):
```js
{ state:"IDLE", spec: resolve("IDLE"), until: Infinity, behaviorId: null, offline: false,
  anchor: null, lastSound: null, priorityLevel: "?", flightChain: [], pos: new THREE.Vector3(0,0.3,0) }
```

Bubble: `showBubble(context)` is a no-op unless `context.body_preview`; `speaker =
context.sender_name || "unknown"`; auto-hide after **7000 ms**; `showDeveloperBubble(context)` uses
`resolveDeveloperBubble` and its own duration. `positionBubble()` (called every frame while
visible):
```js
const head = new THREE.Vector3(fly.position.x, fly.position.y + 0.7, fly.position.z).project(camera);
const x = (head.x*0.5 + 0.5) * innerWidth, y = (-head.y*0.5 + 0.5) * innerHeight;
bubble.style.left = `${clamp(x, 172, innerWidth - 172)}px`;
bubble.style.top  = `${clamp(y, 128, innerHeight - 24)}px`;
```

`playState(state)`: stores `runtime.state/spec`, clears `runtime.anchor`, plays `spec.sound` once
(guarded by `runtime.lastSound`), then
`runtime.until = duration_ms > 0 ? now + duration_ms : requires_ack ? Infinity : now + 60000`;
updates `#state` to `` `${state} · ${priorityLevel.toLowerCase()}` ``.

`applyDecision(decision)`:
```js
let state = decision.fetch || "IDLE";
if (state === "FLYING") { runtime.flightChain = ["TAKEOFF","FLYING","LANDING"]; state = "TAKEOFF"; }
runtime.behaviorId    = decision.behavior_id || runtime.behaviorId;
runtime.priorityLevel = decision.priorityLevel || "?";
playState(state);
```
`applyDeveloperEvent(msg)`: `applyDecision({...msg.decision, behavior_id: msg.behavior_id})`, set
`runtime.anchor = anchorFor(msg.context)`, and if a bubble resolves extend `runtime.until` to
`now + resolved.durationMs`.

`returnToIdle()`:
```js
if (runtime.spec.requires_ack && performance.now() < runtime.until) return;   // IMPORTANT holds until ack
if (runtime.flightChain.length) { playState(runtime.flightChain.shift()); return; }
runtime.state = "IDLE"; runtime.spec = resolve("IDLE"); runtime.anchor = null;
runtime.lastSound = null; runtime.until = performance.now() + 1500;
stateLabel.textContent = "IDLE"; hideBubble();
```

`tickLoop()` — order and math (this is the part with a real historical bug; get it right):
1. base position easing, **decoupled from per-frame animation offsets**:
```js
const target = positionOf(runtime.anchor || spec.position);
const ease = Math.min(1, spec.speed * 0.02);
runtime.pos.x += (target[0] - runtime.pos.x) * ease;   // and y, z
```
2. `fly.visible = spec.visibility !== "hidden"`; opacity `bright 1.0 | normal 0.85 | low 0.55 | dim 0.4`,
   applied only to materials with `transparent === true`.
3. wing flap: `flapRate = 8 + spec.speed*14`, `flapAmp = 0.35 + spec.speed*0.45`; folded
   (`wingL.rotation.x = -1.0`, `wingR.rotation.x = 1.0`) when `animation` is `perch` or `slow_pulse`,
   else `-sin(t*flapRate)*flapAmp` / `+sin(t*flapRate)*flapAmp`.
4. per-animation `extra` + `squash` (all amplitudes exact):
| animation | effect |
|---|---|
| `hover` | `extra.y += sin(t*1.6)*0.03` |
| `perch` | `squash = 1 + sin(t*1.1)*0.05`; `rotation.z = sin(t*0.9)*0.02` |
| `drift` | `extra.x = sin(t*0.7)*0.25` |
| `perk` | `extra.y = max(0,sin(t*3.0))*0.15`; `rotation.z = sin(t*2.5)*0.12` |
| `tilt` | `rotation.z = cos(t*2.0)*0.3` |
| `hover_tilt` | `rotation.z = sin(t*2.0)*0.12`; `extra.y += sin(t*1.2)*0.02` |
| `stutter` | `step = floor(t*2.2)%2`; `extra.z = step===0 ? 0.08 : -0.04` |
| `spin` | billboard: `rotation.z = sin(t*2.0)*0.2`; else `rotation.y += spec.speed*0.05` |
| `pulse` | `squash = 1 + sin(t*3.0)*0.12` |
| `zoom_alert` | `extra.z = max(0,sin(t*3.5))*0.12`; `rotation.z = sin(t*6.0)*0.18` |
| `pacing` | `extra.x = sin(t*1.4)*0.4` |
| `happy_bounce` | `extra.y = abs(sin(t*6.0))*0.2`; `rotation.z = 0` |
| `shake` | `extra.x = (Math.random()-0.5)*0.2`; `extra.y = (Math.random()-0.5)*0.2` |
| `falter` | `extra.y = -abs(sin(t*3.0))*0.13`; `rotation.z = sin(t*2.0)*0.15` |
| `slow_pulse` | `squash = 1 + sin(t*1.1)*0.05` |
| `lift_off` | `p = min(1,(t%1.2)/1.2)`; `extra.y = p*0.35`; `rotation.x = -p*0.25` |
| **`fly_circle`** | `extra.x = cos(t*1.5)*0.4`; `extra.z = sin(t*3.0)*0.12`; `extra.y = sin(t*2.2)*0.16`; billboard: `rotation.z = sin(t*1.2)*0.25`; else `rotation.y += spec.speed*0.06` — the **1.5 / 3.0 x-z pair is the figure-eight** |
| `swoop` | `phase = (t%1.2)/1.2`; `extra.y = -min(1,phase)*0.35`; `rotation.x = min(1,phase)*0.2` |
| `circle` | `extra.x = cos(t*0.9)*0.05`; `extra.z = sin(t*0.9)*0.05` |
5. **apply base + offset (this single line is the fix for a real bug — see §8.2):**
```js
fly.position.copy(runtime.pos).add(extra);
```
6. world clamp: `x ∈ [-3.6, 3.6]`, `y ∈ [-0.9, 2.2]`, `z ∈ [-2.4, 2.0]`.
7. **screen-space clamp** (keeps the sprite out of the left HUD 170 px, the right 320 px panel,
   and the top 90 px):
```js
const spriteW = fly.userData.billboard ? 0.14 : 0.1;
const spriteH = fly.userData.billboard ? 0.13 : 0.09;
const ndc = new THREE.Vector3(fly.position.x, fly.position.y, fly.position.z).project(camera);
const leftLimit  = ((170 / innerWidth) * 2 - 1) + 0.06;
const rightLimit = ((innerWidth - 320) / innerWidth) * 2 - 1 - spriteW;
const topLimit   = (1 - (90 / innerHeight) * 2) - spriteH;
const px = THREE.MathUtils.clamp(ndc.x, leftLimit, rightLimit);
const py = THREE.MathUtils.clamp(ndc.y, -0.86, topLimit);
if (px !== ndc.x || py !== ndc.y) {
  const depth  = Math.max(0.5, fly.position.distanceTo(camera.position));
  const perNdc = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * depth;
  fly.position.y += (py - ndc.y) * perNdc;
  fly.position.x += (px - ndc.x) * perNdc * camera.aspect;
}
```
8. `fly.scale.set(baseScale*squash, baseScale*squash, baseScale)` with `baseScale = spec.scale`.
9. `if (performance.now() >= runtime.until) returnToIdle();`
10. if the bubble is visible → `positionBubble()`; then `renderer.render(scene, camera)`.

WebSocket: `new WebSocket(WS_URL)` with auto-reconnect every **3000 ms**; `ws-dot` background
`#2ecc71` connected / `#e67e22` reconnecting / `#e74c3c` offline; onmessage dispatches
`developer_event` → `applyDeveloperEvent`, `fly_behavior` → `applyDecision({...msg.decision,
behavior_id: msg.behavior_id})` + `showBubble(msg.context)`; parse failure → `hud-tag` text
`"malformed ws payload"`.

`post(path, body)`: `fetch(API_URL + path, {method:"POST", headers:{"Content-Type":"application/json"},
body: JSON.stringify(body)})`; on non-ok throw `http ${status}`; for `/events` success →
`applyDecision({...data, behavior_id: data.behaviorId})` (**camelCase `behaviorId` from REST vs
snake_case over WS**); on failure → `setOffline(true)` and, for `/events`, `demoDecision(body)`.

`demoDecision(body)` — local fallback map mirroring the Python `NATURAL_STATE`:
`important_message→IMPORTANT, warning→WARNING, process_completed→SUCCESS, process_failed→ERROR,
user_message→LISTENING, task_reminder→ATTENTION, calendar_event→IMPORTANT, notification→ATTENTION,
app_open→CURIOUS, app_idle→IDLE`, default `priority >= 0.7 ? "IMPORTANT" : "IDLE"`.
**Flight override:** read `document.getElementById("flight-mode")?.checked`; if checked and the
state is `SUCCESS` or `CURIOUS` and `(body.priority ?? 0.5) >= 0.3` → `state = "FLYING"`.
Then `applyDecision({fetch: state, priorityLevel: "LOCAL", behavior_id: `local_${body.event}`})`.

`wireControls()`: `event-picker` options carry default priorities
(`important_message 0.9, warning 0.95, process_completed 0.7, process_failed 0.6, user_message 0.5,
task_reminder 0.6, calendar_event 0.8, notification 0.4, app_open 0.3, app_idle 0.1`) but do **not**
auto-assign the slider. `priority` `input` updates `#priority-value` to 2 decimals. `#send` builds
`context = {topic: topic.value.trim() || "general", urgency: "medium"}` (+ `body_preview` and
`sender_name: "Demo"` when `#msg` is non-empty), posts to `/events` with `source: "demo"`, and
toasts. `#demo-cycle` forces offline and cycles `["IMPORTANT","THINKING","SUCCESS","CURIOUS","IDLE"]`
every **2600 ms**, then IDLE. Feedback buttons post `/feedback` with
`{behaviorId: runtime.behaviorId || "behavior_demo", feedback}` and toast the reward + synapse count.
`#dev-mode`: `syncDevMode()` GETs `/developer/mode`; change → POST `/developer/mode {enabled}`.
**`#flight-mode`**: `syncFlight()` GETs `/mode/flight` → `checked = !!data.flight` (on failure
`setOffline(true)`); change → POST `/mode/flight {flight: checked}`; toast
`Flight mode <b>ON|OFF</b> — fly uça bilər (free flight) | oturur, sadəcə eventə reaksiya`.

Bootstrap order (bottom of file, exact): `wireControls(); connect(); setOffline(false); tickLoop();`

`desktop/models/`: `fly.png` = 3000×3000 RGBA, **36 MB** (git-ignored; optional billboard texture —
the renderer must work with or without it), `Fly_uv_Lowpoly.obj` (594 v / 568 f, LightWave export,
reserved for a future 3D pass, currently unused), `Fly_uv.jpg` (1024×1024 UV map, unused).

`desktop/test/` (`node --test`, ESM, `node:test` + `node:assert/strict`, 20 tests):
- `animations.test.mjs`: a spec exists for all backend states (`IDLE, BACKGROUND, ATTENTION, CURIOUS,
  THINKING, PROCESSING, IMPORTANT, WARNING, SUCCESS, ERROR, WAITING, SLEEPING, LISTENING,
  LEARNING`); IMPORTANT is `bright`/scale `1.5`/speed `0.9`/position `attention_area`/duration
  `8000`; unknown state → `animation === "perch"` and `fallback === true`; SLEEPING → `dim` +
  `corner_low`; all `POSITIONS` values are numeric triples.
- `developer.test.mjs` (11 tests): `resolveDeveloperBubble(null|{})` → `null`; text verbatim;
  `durationMs` from `bubble_ms` else `DEFAULT_BUBBLE_MS`; `speaker` `"WARNING · Possible null
  reference"`; title fallback `"WARNING · developer.bug_detected"`; `"Warning"` → uppercased;
  `meta === "companion-app / src/auth/login.ts:42:10"`; `meta === ""` when all location fields are
  null; `anchorFor` → `"code_2"`, passes arbitrary anchors through, `null` for undefined/""/null.
- `sound.test.mjs`: every `STATE_SPEC[*].sound` resolves to a preset whose notes have `f > 0` and
  `dur > 0`; exact mapping `IMPORTANT→soft_chime, SUCCESS→success, WARNING→chime, ERROR→error`,
  `IDLE.sound === undefined`; `describeSound("bogus"|""|undefined)` → `null`; `success` has ≥3 notes
  and `success[2].f > success[0].f`.

---

# PART 5 — WHATSAPP GATEWAY

`whatsapp-gateway/` is an isolated Node service (not part of the build/test): it uses
`whatsapp-web.js`, reads a QR once, and forwards normalized messages to
`http://localhost:8080/api/v1/whatsapp/webhook` (configurable via `FLY_BACKEND_URL`).
Session dir `.wwebjs_auth/` is git-ignored. **Three.js must never parse WhatsApp messages** — the
backend normalizes type → event + priority, and only an 80-char `body_preview` is forwarded.

---

# PART 6 — PYTHON TESTS (99 total, `python3 -m unittest discover -s tests -q`)

12 files under `connectome/tests/`: `test_loader, test_simulation, test_state_machine,
test_policy, test_event_processor, test_reward, test_store, test_influence, test_server,
test_dataset, test_evaluation, test_rl_experiment`. All stdlib `unittest`, no pytest.

Required behavior highlights (these are the assertions; implement them):
- **test_policy**: every `PATTERNS` key == every `states` key; `PRIORITY_LEVEL` covers all states;
  natural-state boost selects the fitting state (pass `flight=False` for that assertion);
  `test_flight_disabled_never_picks_flight_states` — with `flight=False` the returned state is never
  in `FLIGHT_STATES` **and** `assertIn("FLYING", decision["scores"])`;
  `test_fresh_celebration_event_flies_when_flight_on` — a cold brain + `process_completed` with
  `flight=True` → `FLYING`; with `flight=False` → `SUCCESS`;
  `test_calm_low_priority_celebration_stays_grounded` — `app_open` at priority `0.2` stays `CURIOUS`;
  `test_serious_event_never_flies` — IMPORTANT/ERROR/WARNING never fly.
- **test_server**: `test_flight_mode_defaults_on`; `test_flight_off_excludes_flight_states`; malformed
  bodies never 500; `/health`, `/states`, `GET /mode`, `POST /mode`, `/reset` shapes.
- **test_dataset**: code tables, label mapping, `behavior_id` join (exact equality — no prefix
  stripping; there is a regression test for the old `behavior_`-prefix mismatch), `write_dataset`
  returns exactly 3 paths in `[csv, jsonl, meta]` order.
- **test_evaluation**: every prior sums to `1.0` (`places=6`); `expected_reward("text") == 0.265`;
  `penalized_reward("audio") < 0`; **`graded_reward("image","frontflip") == graded_reward("image",
  "face_user") == expected_reward("image")`** (all ENGAGED reactions score the same — this is
  intentional); `STATE_REACTION` covers all 17 states; `baseline_reactions()` keys == `SCENARIOS`
  keys and every value ∈ `ENGAGED ∪ {NORMAL}`; verdict ladder: identical → `CANDIDATE_FOR_PRODUCTION`
  + `safe_to_influence_production is True`; divergent but non-degrading → `COLLECT_MORE_DATA`;
  degrading → `KEEP_BASELINE`; `load_rl_reactions` raises `FileNotFoundError` for a missing snapshot
  (and the Faza-5 snapshot **must exist on disk** for that test — run `offline_exp` first).
- **test_rl_experiment** (torch-free stubs!): `MESSAGE_CASES` names == the 5 cases;
  `baseline_behavior(1.0)==1, (3.0)==2, (0.0)==3, (2.0)==3`;
  `type_code_of("image")==1.0, ("ptt")==2.0, ("sticker")==3.0, ("chat")==0.0`;
  a stub returning `baseline_behavior` scores `policy_agreement == 1.0`; an always-`face_user` stub
  scores `0.4` (2/5); a label-sequence stub scores 2/5; `sample_goal_for_type` stays in
  `[0.02, 0.98]`.
- **test_influence**: mode gating (`off`/`auto`/`on`), verdict requirements, coverage, no-op when
  the learned state equals the baseline state, baseline preserved on every failure path.

---

# PART 7 — RUN COMMANDS

```bash
# Python brain (stdlib only, Py >= 3.11; reference env: 3.14.7)
cd connectome
python3 -m unittest discover -s tests -q                      # 99 tests
python3 -m connectome.server --port 8601 --steps 40 --flight on
python3 -m connectome.simulate --event important_message --priority 0.9 --source whatsapp \
        --context '{"topic":"job","urgency":"high"}' --feedback marked_useful --json

# Dataset export
python3 -m connectome.training.dataset --db ~/.fly/connectome.db

# Offline RL + Phase-6 gate (torch REQUIRED — use the venv, never the system python)
python3 -m venv .venv
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU wheel!
.venv/bin/python -m connectome.training.rl.offline_exp --episodes 4000
.venv/bin/python -m connectome.training.evaluation

# Backend
cd backend && mvn test && mvn spring-boot:run                 # Java 21, port 8080

# Desktop
cd desktop && npm install && node --test test/ && npm start
FLY_SMOKE=1 npx electron .                                      # prints FLY_SMOKE_OK
```

**Torch note (learned the hard way):** the default PyPI `torch` wheel pulls ~2.8 GB of CUDA
dependencies and fails on this machine with `OSError: [Errno 122] Disk quota exceeded`. Always use
the CPU index (`download.pytorch.org/whl/cpu`, ~250 MB). torch 2.14.0+cpu works on Python 3.14
without numpy (it prints a harmless `Failed to initialize NumPy` warning). Production inference
never needs it.

**Operations notes:** start Python and Spring as detached background services and stop them by PID
(`ss -ltnp` then `kill <pid>`). **Never `pkill -f electron`** — it kills unrelated processes and can
hang. The user only ever runs `cd desktop && npm start`.

---

# PART 8 — KNOWN ISSUES & REMAINING WORK (important context)

## 8.1 The RL baseline inconsistency (OPEN, the main thing to decide)
There are **two different baselines**, and this is a genuine structural bug, not a typo:

- **Baseline A** — `rl_brain.baseline_behavior(type_code)`: a fixed media-type table
  (`image→frontflip`, `sticker→backflip`, `text`/`audio→face_user`). Used as the **training
  target** in `offline_exp.warm_up` and as the ground truth in `offline_exp.evaluate`, which is why
  the Faza-5 report says 80% agreement.
- **Baseline B** — `evaluation.baseline_reactions()`: the **real brain** (`load_wiring` + `Brain` +
  40 steps + `decide`) mapped through `STATE_REACTION`. It returns `face_user` for **all five**
  scenarios (because `user_message→LISTENING` and `notification→ATTENTION`, and both map to
  `face_user`), which is why the Phase-6 report says 20% agreement and the verdict is
  `COLLECT_MORE_DATA`.

Root cause: `SCENARIOS` collapses four media types (`image/audio/sticker/video`) onto the single
internal event `notification`, and `__event()` puts no `media_type` in `context` — so the brain
*cannot* express a per-media reaction. Baseline A asks for something the event contract cannot carry.
And because `graded_reward` scores every ENGAGED reaction identically, the reward channel cannot
express the difference either — so the gate is structurally unreachable, not merely unpassed.

**Decision options (ask the human before choosing):**
- (a) Point the RL target at the real brain. Would require: move `STATE_REACTION` into a
  torch-free shared leaf module (so `rl_brain` can import it without pulling in the 2414-neuron
  wiring); recompute `MESSAGE_CASES` labels and `warm_up`'s `target_behav` from that single source;
  decide whether `graded_reward` should discriminate between engaged reactions; decide whether
  `SCENARIOS` should carry `context.media_type`; then update `test_rl_experiment`
  (`test_baseline_behavior_mapping`, `test_evaluate_zero_agreement_when_degenerate`) and
  `test_evaluation`; re-run `offline_exp` then `evaluation`.
- (b) Collect more real feedback in the app and re-export the dataset (does **not** by itself fix
  the A/B contract mismatch; `offline_exp` would also need wiring to read the dataset).
- (c) Force `FLY_LEARNED_INFLUENCE=on` — bypasses the gate and contradicts the design principle.
  **Not recommended.**

Note: `influence.py` maps `frontflip → IMPORTANT` and `backflip → WARNING`; if the gate were forced
open, an incoming `image` (which the brain treats as `ATTENTION`) would be escalated to `IMPORTANT`
(priority 7, 8 s, sound, `requires_ack`) — a real behavior change hidden behind a shut gate.

## 8.2 The animation offset accumulation bug (FIXED — do not reintroduce)
Animations used to add their offsets **directly to `fly.position` every frame** while the
position easing was weak (`spec.speed * 0.02` → `0.014`). Positive offsets therefore accumulated and
the fly climbed to the `y = 2.2` world clamp and appeared stuck against the top border; a
`process_completed` bounce reached `worldY 2.14` instead of the intended `0.30–0.45`. The fix is the
separation of the eased **base** position `runtime.pos` from the per-frame `extra` offsets, which
are recomputed from scratch each frame and never accumulated:
```js
fly.position.copy(runtime.pos).add(extra);
```
The screen-space clamp (§4 renderer step 7) is the second layer that keeps the sprite out of the
HUD and the control panel. Verify after any animation change that a `process_completed` bounce
stays around `worldY 0.30–0.45`.

## 8.3 Latent bugs deliberately left in place (document them, don't "fix" silently)
- `BehaviorGateway.setFlight` failure path calls `Map.of("flight", null, ...)` which throws NPE
  (use a null-tolerant map).
- `state_machine.DEFAULT_TRANSITIONS` makes IDLE able to transition to any of the 16 named states.
- `influence.py` `EVENT_TO_CASE` is dead code (documentation of intended defaults).
- `evaluation.baseline_reactions(events=...)` accepts and ignores its `events` parameter.
- `simulate.run_simulation`'s `synapse_delta` returns the **new weight** (tuple keys) while
  `server.feedback` returns the **difference** (`"KC->MBON_x"` string keys) — intentionally not
  unified.
- `event_processor._safe_priority` lets the string `"nan"` through as NaN (all downstream
  comparisons are then False, so the state degrades safely).
- `ApiExceptionHandler` has no `HttpMessageNotReadableException` handler → malformed JSON = 500.
- `POST /api/v1/mode/flight` is intentionally outside the token interceptor's path list.
- `offline_exp` never reads `train_decisions.*` — the dataset branch is observability only.

## 8.4 Optional polish (not done)
- `desktop/models/fly.png` is 36 MB → resize/compress to ~1–2 MB.
- `FLY_SMOKE`-style CI wiring; README is the only doc besides `doc/`.
- Note for whoever continues: the assistant doing this work **cannot read images** — for visual bugs
  prefer renderer instrumentation or ask the human for a text description of what they see.

---

# PART 9 — ACCEPTANCE CRITERIA

The rebuild is done when:
1. `cd connectome && python3 -m unittest discover -s tests -q` → **99 tests, OK** (torch not required).
2. `cd backend && mvn test` → all Java tests OK on Java 21.
3. `cd desktop && node --test test/` → **20 tests, OK**; `FLY_SMOKE=1 npx electron .` prints
   **`FLY_SMOKE_OK`**.
4. `python3 -m connectome.server --port 8601` then `curl localhost:8601/health` returns
   `status: "ok"`, `neurons: 2414`, `flight_mode: "on"` (or `"off"` with `--flight off`).
5. `GET/POST localhost:8601/mode` round-trips `{"flight": bool}`; with flight on,
   `process_completed` @ priority ≥ 0.3 returns `fetch: "FLYING"`, and `important_message` /
   `warning` @ high priority return `IMPORTANT` / `WARNING` (never `FLYING`).
6. Spring on :8080: `GET /api/v1/health` returns `status UP` when Python is reachable, `DEGRADED`
   (never an error status) when it is not; `POST /api/v1/events` broadcasts
   `{"type":"fly_behavior","behavior_id","decision","context"}` on `ws://localhost:8080/ws/fly` with
   `behavior_id` exactly equal to the event id that reached Python.
7. `python3 -m connectome.training.rl.offline_exp --episodes 4000` writes
   `brain_model.pt` + `rl_experiment_latest.json`; `python3 -m connectome.training.evaluation`
   writes `evaluation_latest.json` with a **non-`CANDIDATE_FOR_PRODUCTION` verdict** so the
   production gate stays shut by default (§8.1).
8. The desktop app renders: bubble above the fly's head, the fly never clips the window border or
   hides under the HUD/panel, and a `process_completed` event plays
   `TAKEOFF → FLYING → LANDING → IDLE` with the flight checkbox enabled.
9. Nothing is committed to git.
