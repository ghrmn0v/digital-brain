"""Faza 6: offline evaluation of the learned policy against the deterministic baseline.

Runs the real rule-based baseline (the connectome brain + policy.decide) and the
trained RL policy (loaded from the Faza 5 snapshot) on the WhatsApp message-type
scenarios. Each reaction is scored through a user-feedback preference model built
on the project's REWARD_MAP.

Phase 7 gate: production influence is only allowed when the learned policy does not
degrade expected reward below the baseline ("Never replace a working deterministic
baseline with an untested ML model").
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Sequence

from connectome.model import Brain
from connectome.loader import load_wiring
from connectome.policy import decide
from connectome.reward import REWARD_MAP
from connectome.simulate import inject_event
from connectome.training.rl.rl_brain import BEHAVIORS  # noqa: F401  (documents the coarse label set)

# ---------------------------------------------------------------------------
# Scenarios and user-feedback preference model (offline prior, not production).
# type -> (event name in the internal contract, event priority, feedback prior)
# ---------------------------------------------------------------------------
SCENARIOS: Dict[str, Dict[str, Any]] = {
    "text":    {"event": "user_message", "priority": 0.40, "media_type": None,
               "prior": {"reacted_positive": 0.30, "looked": 0.25, "ignored": 0.35, "dismissed": 0.10}},
    "image":   {"event": "notification", "priority": 0.75, "media_type": "image",
               "prior": {"reacted_positive": 0.45, "looked": 0.30, "ignored": 0.15, "dismissed": 0.10}},
    "audio":   {"event": "notification", "priority": 0.85, "media_type": "audio",
               "prior": {"marked_useful": 0.40, "reacted_positive": 0.25, "looked": 0.20, "ignored": 0.10, "dismissed": 0.05}},
    "sticker": {"event": "notification", "priority": 0.60, "media_type": "sticker",
               "prior": {"reacted_positive": 0.35, "looked": 0.30, "ignored": 0.25, "dismissed": 0.10}},
    "video":   {"event": "notification", "priority": 0.75, "media_type": "video",
               "prior": {"reacted_positive": 0.45, "looked": 0.30, "ignored": 0.15, "dismissed": 0.10}},
}

# Presentation-level reaction classes shared by both policies.
ENGAGED = frozenset({"face_user", "frontflip", "backflip"})
NORMAL = "normal"

# Fly state -> reaction class (so the rule baseline and the RL labels line up).
STATE_REACTION: Dict[str, str] = {
    "IDLE": NORMAL, "BACKGROUND": NORMAL, "SLEEPING": NORMAL,
    "THINKING": NORMAL, "PROCESSING": NORMAL, "LEARNING": NORMAL,
    "LANDING": NORMAL,
    "TAKEOFF": "face_user", "FLYING": "face_user",
    "LISTENING": "face_user", "ATTENTION": "face_user", "CURIOUS": "face_user",
    "IMPORTANT": "frontflip", "WAITING": "frontflip", "SUCCESS": "frontflip",
    "WARNING": "backflip", "ERROR": "backflip",
}

REPORT_DIR = Path(__file__).parent / "evaluation_reports"
DEFAULT_SNAPSHOT = Path(__file__).parent / "rl" / "experiments" / "rl_experiment_latest.json"


# ---------------------------------------------------------------------------
# Reward math (pure, testable)
# ---------------------------------------------------------------------------
def expected_reward(type_: str) -> float:
    """Reward ceiling when the reaction captures the user's attention as expected."""
    return round(sum(p * REWARD_MAP[k] for k, p in SCENARIOS[type_]["prior"].items()), 4)


def penalized_reward(type_: str) -> float:
    """Expected reward when the fly does NOT react (user turns to ignore/dismiss)."""
    prior = SCENARIOS[type_]["prior"]
    positive_mass = sum(p for k, p in prior.items() if REWARD_MAP[k] > 0)
    dismiss_mass = sum(p for k, p in prior.items() if REWARD_MAP[k] <= 0)
    return round(positive_mass * REWARD_MAP["dismissed"] + dismiss_mass * REWARD_MAP["ignored"], 4)


def graded_reward(type_: str, reaction: str) -> float:
    """Reward a reaction earns: engagement wins, no-reaction loses."""
    if reaction in ENGAGED:
        return expected_reward(type_)
    return penalized_reward(type_)


# ---------------------------------------------------------------------------
# Baseline reactions (real brain, deterministic, stdlib-only)
# ---------------------------------------------------------------------------
def baseline_reactions(events: Sequence[str] | None = None) -> Dict[str, str]:
    graph = load_wiring()
    reactions: Dict[str, str] = {}
    for name, spec in SCENARIOS.items():
        brain = Brain(graph)
        event = __event(name, spec)
        inject_event(brain, event)
        for _ in range(40):
            brain.step()
        state = decide(brain, event)["state"]
        reactions[name] = STATE_REACTION.get(state, NORMAL)
    return reactions


def __event(name: str, spec: Dict[str, Any]):
    from connectome.event_processor import Event

    context: Dict[str, Any] = {
        "urgency": "high" if spec["priority"] >= 0.7 else "medium"
    }
    media = spec.get("media_type")
    if media:
        context["media_type"] = media
    return Event(
        id=f"eval_{name}",
        name=spec["event"],
        source="whatsapp",
        priority=spec["priority"],
        person=None,
        context=context,
        timestamp=0.0,
    )


# ---------------------------------------------------------------------------
# Learned policy reactions (from the Faza 5 snapshot)
# ---------------------------------------------------------------------------
def load_rl_reactions(snapshot: Path = DEFAULT_SNAPSHOT) -> Dict[str, str]:
    if not snapshot.exists():
        raise FileNotFoundError(
            f"no RL policy snapshot at {snapshot}; run offline_exp first"
        )
    data = json.loads(snapshot.read_text())
    rows = data["evaluation"]["rows"]
    return {row["case"]: row["rl_behavior"] for row in rows}


# ---------------------------------------------------------------------------
# Comparison and verdict
# ---------------------------------------------------------------------------
def evaluate(
    baseline: Dict[str, str],
    learned: Dict[str, str],
    cases: Sequence[str] | None = None,
) -> Dict[str, Any]:
    cases = cases or list(SCENARIOS.keys())
    rows = []
    agreed = 0
    reward_deltas = []
    for name in cases:
        base = baseline.get(name, NORMAL)
        rl = learned.get(name, NORMAL)
        agree = base == rl
        agreed += int(agree)
        r_base = graded_reward(name, base)
        r_rl = graded_reward(name, rl)
        reward_deltas.append(r_rl - r_base)
        rows.append({
            "case": name,
            "priority": SCENARIOS[name]["priority"],
            "baseline_reaction": base,
            "rl_reaction": rl,
            "agree": agree,
            "reward_baseline": r_base,
            "reward_rl": r_rl,
            "reward_delta": round(r_rl - r_base, 4),
        })

    total = len(cases)
    agreement = agreed / total if total else 0.0
    mean_delta = sum(reward_deltas) / total if total else 0.0
    degraded = any(delta < 0 for delta in reward_deltas)

    if agreed >= total:
        verdict = "CANDIDATE_FOR_PRODUCTION"
        safe_to_expose = True
    elif degraded:
        verdict = "KEEP_BASELINE"
        safe_to_expose = False
    else:
        verdict = "COLLECT_MORE_DATA"
        safe_to_expose = False

    return {
        "compared_cases": total,
        "policy_agreement": round(agreement, 4),
        "mean_reward_delta_vs_baseline": round(mean_delta, 4),
        "degraded_cases": degraded,
        "verdict": verdict,
        "safe_to_influence_production": safe_to_expose,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# CLI + report
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Faza 6: evaluate learned policy vs baseline")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    baseline = baseline_reactions()
    learned = load_rl_reactions(args.snapshot)
    result = evaluate(baseline, learned)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / "evaluation_latest.json"
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"policy agreement vs baseline: {result['policy_agreement']:.0%}")
        print(f"mean reward delta:           {result['mean_reward_delta_vs_baseline']:+.4f}")
        print(f"degraded cases:              {result['degraded_cases']}")
        print(f"verdict:                     {result['verdict']}")
        print(f"safe to influence production:{result['safe_to_influence_production']}")
        for row in result["rows"]:
            print(f"  {row['case']:<8} baseline={row['baseline_reaction']:<10} "
                  f"rl={row['rl_reaction']:<10} reward {row['reward_baseline']:+.3f}->{row['reward_rl']:+.3f}")
        print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())