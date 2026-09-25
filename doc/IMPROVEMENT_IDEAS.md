# Improvement ideas — Fly / Connectome

Measured findings on the connectome model. Items marked ✅ are implemented,
⚠️ are implemented but do **not** deliver what was originally claimed, ⛔ are
blocked on an external credential, 🔶 need a decision, and ⏭️ are deferred.

This document records what was measured, including the results that did not
work. The negative results are the valuable part: they stop the same
hypotheses being re-proposed.

## Summary

| # | Idea | Status | Where |
|---|---|---|---|
| 1 | Real `weight` on the initial KC→MBON wiring | ✅ Implemented | `adult_mb_wiring.json`, `loader.py`, `model.py` |
| 2 | `media_type` channel | ⚠️ Implemented, but the gate stays closed | `simulate.py`, `evaluation.py` |
| 3 | `MBON_gamma → MBON_output` inhibitor | ✅ Implemented | `adult_mb_wiring.json`, `model.py` |
| 4 | Constant bias → stochastic noise | ✅ Implemented | `model.py` |
| 5 | Eligibility trace (associative learning) | ✅ Implemented (code was broken) | `model.py` |
| 6 | Per-person channel | ⚠️ Implemented, but there is no per-person response | `simulate.py` |
| 7 | Real FlyWire data (CAVEclient) | ⛔ Blocked on a token | `reference/flywire_live_service.py` |
| 8 | RL baseline mismatch | 🔶 Needs a decision | `training/rl/rl_brain.py`, `evaluation.py` |
| 9 | Memory consolidation | ⏭️ Deferred | — |

---

## 1. ✅ Real initial weight (implemented)

The initial KC→MBON weights were a flat bias. The adult FlyWire export carries
real per-synapse weights, so the loader reads them.

**Done:**
- `adult_mb_wiring.json` now carries a real `weight` per edge.
- `model.py`: `decay` is now applied against **`initial_weights`**, not 1.0
  (`updated -= decay * (current - prior)`). Otherwise the 1.4/0.6 values
  drifted back toward 1.0 after a few hundred feedback events and the biological
  prior was lost.

**Result:** `{MBON_alpha: 0.6, MBON_beta: 1.0, MBON_beta2: 1.0, MBON_gamma: 1.4,
MBON_apostrophe: 1.0, MBON_bpost: 1.0, MBON_output: 1.2}`

---

## 2. ⚠️ `media_type` channel — implemented, but the gate does not open

**Original claim:** *"This alone lets the brain distinguish image vs. audio
events and makes the RL training meaningful."*

**That claim is not correct.** Measured:

```
notification + topic + urgency (no media_type)  -> CTX drive 0.4500
notification + image                             -> CTX drive 0.5250
notification + audio                             -> CTX drive 0.5250
notification + sticker                           -> CTX drive 0.5250
notification + video                             -> CTX drive 0.5250
```

**Every media type produces the same value.** The cause is architectural:

1. The brain has a **single `CTX` node**, which produces a scalar drive
   (`0.15 + 0.6 * covered/8`). `media_type` only changes the *count* of
   covered channels (3→4); **which** channel was selected is lost.
2. There is a single `KC` group (population 2200), so `_activity_fn` can
   compute KC activity but cannot tell **which KC sub-population** activated.
3. `policy.PATTERNS` only inspects MBON compartments and has no general
   information about `media_type`.

So media type reaches the brain only as "this event carries slightly more
context". An image and a sound are treated identically.

**Done (still useful, but not the claimed effect):**
- `simulate.py` → `_context_channels(..., ctx.get("media_type", ""))`
- `evaluation.py` → every scenario now carries its own `media_type` (`image`,
  `audio`, `sticker`, `video`), so the comparison runs over the **same inputs**.
  Previously a scenario claimed "audio" while the brain never received audio.

**Real fix (merge with idea 8):** `PATTERNS` needs a media-aware readable
component — for example a **separate KC group per media type** (`KC_image`,
`KC_audio`, …) or a direct MBON input driven by `media_type`. This is an
**architecture change**, not a five-line patch.

**Status:** `baseline_reactions()` still returns `face_user` (5/5), so the gate
stays closed.

---

## 3. ✅ `MBON_gamma → MBON_output` inhibitor (implemented)

In the real fly, the γ-MBONs are the compartment that most strongly criticises
the approach-avoidance output.

**Done:**
- JSON: `{"from": "MBON_gamma", "to": "MBON_output", "synapses": 1500, "plastic": false,
  "physiology": "inhibitory"}`
- `model.py::_drive`:
```python
sign = -1.0 if edge.physiology == "inhibitory" else 1.0
total += sign * edge.synapses * weight * self.activity[edge.source]
```

**Measured effect** (live server, `process_completed`):
`MBON_output = 0.141` versus `0.176` for the other compartments. Previously gamma
boosted the output; it now criticises it, so **avoidance (WARNING/ERROR)
correctly suppresses the output.**

---

## 4. ✅ Stochastic noise (implemented)

Real variability instead of a constant `+0.0005` bias.

**Done:**
```python
# DEFAULT_CONFIG: "noise": 0.0005  -> now a standard deviation
"trace_decay": 0.85,   # new (for idea 5)
"seed": None,          # new: None = non-deterministic; a value is reproducible
```
```python
# _drive()
drive += self._rng.gauss(0.0, self.config["noise"])
```
`Brain` owns its own `random.Random(seed)` stream — the global `random` is not
touched. Tests and experiments are reproducible with `config={"seed": 7}`.

**Note:** `noise` is no longer a *bias* but a *standard deviation*. The value is
small (0.0005) and does not practically move decisions, but the same event at
the same priority no longer produces a bit-identical result every time.

---

## 5. ✅ Eligibility trace (implemented — the code was broken)

**The code in the proposal was wrong:** `self.eligibility` was built keyed by
`edge.key` (a tuple), but `_update_plasticity` read
`self.eligibility.get(edge.source, 0.0)` — **a dictionary keyed by tuple was
being read with a string**, so it was always `0.0` and the trace never ran.

**Done (correctly):**
```python
# Brain.__init__
self.eligibility = {edge.key: 0.0 for edge in graph.edges.values() if edge.plastic}

# step() -> after activity is updated
def _update_traces(self):
    decay = self.config["trace_decay"]; keep = 1.0 - decay
    for edge in self.graph.plasticity_edges():
        key = edge.key
        self.eligibility[key] = (decay * self.eligibility.get(key, 0.0)
                                 + keep * self.activity.get(edge.source, 0.0))

# _update_plasticity
kc = self.eligibility.get(key, 0.0)      # was: self.activity.get(edge.source, 0.0)
```
`reset()` clears the traces. `trace_decay = 0.85` → 15% decay per step.

**Measured result:** reward arriving five steps after the event still modifies
the correct synapse (`1.40000 → 1.40051`), so the "late feedback dies" problem
is gone.
**Changed behaviour:** immediate feedback now has a **weaker** effect than
before (because KC activity has not accumulated yet), which matches real
*Drosophila* learning.

---

## 6. ⚠️ Per-person channel — implemented, but there is no per-person response

**Original claim:** *"The fly would literally learn to respond differently to
messages from different people."*

**That claim is also not correct** — the same architectural cause (a single
scalar `CTX` plus a single `KC` group). The measured difference is only a
**general increase**:

| Query | CTX drive | Result |
|---|---|---|
| `user_message` (no person) | 0.375 | LISTENING (conf 0.377) |
| `person_alim` | 0.450 | LISTENING (conf 0.388) |
| `person_boss` | 0.450 | LISTENING (conf 0.390) |

**Done:** `simulate.py` → `person_id = (event.person or {}).get("id", "")` is
now passed into `_context_channels`. For whoever writes the file next, this is
the hook ready for **a separate KC group per person**.

**Real fix:** add `KC_p_<hash>` groups to `nodes` and have `inject_event` select
one — an architecture change.

---

## 7. ⛔ Real FlyWire data (CAVEclient)

Requires a **free flywire.ai account plus an API token**. 50,000+ edges, with
synapse counts accurate at the level of individual neuron pairs.

**Status:** impossible without a token. If a token is provided:
1. Extend `connectome/reference/flywire_live_service.py` (a stub already exists).
2. Write the new JSON with neuron-level edges.
3. `loader.py` **stays unchanged** (the README already says "expandable with real
   FlyWire exports through the same loader") — as long as the new format keeps
   `from/to/synapses/plastic/physiology/weight`, no code change is needed.
4. `PATTERNS` must be revisited for groups with `population` > 1.

---

## 8. 🔶 RL baseline mismatch (open decision)

Left unchanged — this **requires a decision**. There are two different baselines:

- **Baseline A** (`rl_brain.baseline_behavior`): a fixed table — `image→frontflip`,
  `sticker→backflip`. The RL learns on top of it (Phase 5 report: 80%).
- **Baseline B** (`evaluation.baseline_reactions`): the **real brain** — all five
  scenarios return `face_user` (Phase 6 report: 20%, verdict `COLLECT_MORE_DATA`).

Ideas 2 and 6 would improve this comparison but did not **resolve** it, for the
architectural reasons above.

**Options:** (a) aim the RL objective at the real brain and move
`STATE_REACTION` into a torch-free shared leaf module; (b) collect more real
feedback; (c) `FLY_LEARNED_INFLUENCE=on` (passes the demo flow — **not
recommended**).

---

## 9. ⏭️ Memory consolidation (deferred)

Batch update during a "sleep" phase instead of real-time plasticity. New module,
new CLI, new tests. Does not change the Phase 7 gate. Later.

---

## Problem found in passing (not changed in that task)

**`_context_channels` hash collision → behaviour changes with the topic string.**

```
topic "job"/"system"/"general"/"b"/"c" -> 4 channels -> drive 0.4500
topic "work"/"build"/"demo"/"a"        -> 3 channels -> drive 0.3750
```

`CTX_CHANNELS = 8`, split into 4 parts → 3 or 4 unique channels (50/50). The
result: **the same event at the same priority behaves differently depending on
the topic string.** `kc_theta = 0.35` is close to this level, so the threshold
is also affected.

This is existing behaviour (it was not introduced by that change — adding
`media_type`/`person` only widened the existing 0.375 → 0.450 spread). But for
a "learning fly" this is **undesirable** behaviour.

**Possible fixes (a decision is required):**
- Sum **each channel's own drive** instead of the `covered` count (each part
  contributes its own drive, total clamped) — more stable, less collision
  sensitivity.
- Increase `CTX_CHANNELS` (8 → 16/32) → fewer collisions.
- Turn `_context_channels` into a compartment-selecting function (the real fix
  for idea 6).
