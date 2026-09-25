"""Faza 5/6: offline RL experiment + evaluation against the deterministic baseline.

Run with torch available:

    python3 -m connectome.training.rl.offline_exp --episodes 500

The experiment never touches the production inference path (connectome.server) or its
persisted weights. It only warms up the RL network offline and reports policy agreement
with the rule-based baseline on the WhatsApp message-type cases.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from connectome.training.rl.rl_brain import (
    BEHAVIORS,
    baseline_behavior,
    sample_goal_for_type,
    type_code_of,
)

# (case name, whatsapp type code, baseline behavior label)
MESSAGE_CASES: List[Tuple[str, float, int]] = [
    ("text", 0.0, baseline_behavior(0.0)),
    ("image", 1.0, baseline_behavior(1.0)),
    ("audio", 2.0, baseline_behavior(2.0)),
    ("sticker", 3.0, baseline_behavior(3.0)),
    ("video", 1.0, baseline_behavior(1.0)),
]

MODEL_DIR = Path(__file__).parent / "experiments"
DEFAULT_MODEL = MODEL_DIR / "brain_model.pt"


def evaluate(model, cases: Sequence[Tuple[str, float, int]] = MESSAGE_CASES) -> Dict:
    """Report RL vs rule-based baseline agreement per message-type case.

    `model` only needs `predict_behavior(type_code, text_len, cur, goal) -> int`,
    so the experiment can be unit-tested without torch.
    """
    rows = []
    agreed = 0
    cur = (0.5, 0.5)
    for name, type_code, baseline in cases:
        goal = sample_goal_for_type(type_code, 12, cur[0], cur[1])
        rl_label = int(model.predict_behavior(type_code, 12, cur[0], cur[1], goal[0], goal[1]))
        agree = rl_label == baseline
        agreed += int(agree)
        rows.append({
            "case": name,
            "rl_behavior": BEHAVIORS.get(rl_label, "?"),
            "baseline_behavior": BEHAVIORS.get(baseline, "?"),
            "agree": agree,
        })
    total = len(cases)
    return {
        "evaluated_cases": total,
        "agreed_cases": agreed,
        "policy_agreement": round(agreed / total, 4) if total else 0.0,
        "rows": rows,
    }


def warm_up(episodes: int = 4000, model_path: Path = DEFAULT_MODEL) -> Dict:
    """Offline warm-up (direction + behavior heads) copied from the prototype."""
    from connectome.training.rl.rl_brain import FlyWireBrainRL
    import torch
    import torch.nn.functional as F

    brain_model = FlyWireBrainRL()
    optimizer = torch.optim.Adam(list(brain_model.parameters()), lr=1e-2)

    if model_path.exists():
        brain_model.load_state_dict(torch.load(model_path, map_location="cpu"))
        print(f"Resumed from existing checkpoint {model_path}")

    brain_model.train()
    start = time.time()
    losses: List[float] = []
    for ep in range(1, episodes + 1):
        type_code = random.choice([0.0, 0.0, 1.0, 2.0, 3.0])
        text_len = random.uniform(1, 300)
        cur = (random.random(), random.random())
        goal = sample_goal_for_type(type_code, int(text_len), cur[0], cur[1])

        state = torch.FloatTensor([[
            type_code, text_len / 500.0, cur[0], cur[1], goal[0], goal[1],
        ]])
        disp, behav_logits = brain_model.forward(state)

        target_disp = torch.FloatTensor([[
            max(-1.0, min(1.0, goal[0] - cur[0])),
            max(-1.0, min(1.0, goal[1] - cur[1])),
        ]])
        target_behav = torch.LongTensor([baseline_behavior(type_code)])

        loss = F.mse_loss(disp, target_disp) + 0.5 * F.cross_entropy(behav_logits, target_behav)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if ep % 400 == 0:
            losses.append((ep, round(float(loss), 4)))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    brain_model.eval()
    torch.save(brain_model.state_dict(), model_path)
    return {
        "episodes": episodes,
        "duration_s": round(time.time() - start, 2),
        "checkpoint": str(model_path),
        "loss_curve": losses,
    }


class TorchModel:
    """Adapter exposing predict_behavior over the torch network (needs torch)."""

    def __init__(self, model_path: Path = DEFAULT_MODEL, train_steps: int = 800):
        import torch

        from connectome.training.rl.rl_brain import FlyWireBrainRL

        self.net = FlyWireBrainRL()
        if model_path.exists():
            self.net.load_state_dict(torch.load(model_path, map_location="cpu"))
        self.net.eval()
        self.torch = torch
        self.sanity = train_steps

    def predict_behavior(self, type_code, text_len, cur_x, cur_y, goal_x, goal_y) -> int:
        state = self.torch.FloatTensor(
            [[type_code, text_len / 500.0, cur_x, cur_y, goal_x, goal_y]]
        )
        with self.torch.no_grad():
            _, behav_logits = self.net.forward(state)
            return int(self.torch.argmax(behav_logits[0]).item())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline RL experiment vs deterministic baseline")
    parser.add_argument("--episodes", type=int, default=4000)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    train = warm_up(args.episodes, args.model)
    model = TorchModel(args.model)
    metrics = evaluate(model)

    out = {"train": train, "evaluation": metrics}
    report = MODEL_DIR / "rl_experiment_latest.json"
    report.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"warm-up: {train['episodes']} episodes in {train['duration_s']}s")
        print(f"policy agreement vs baseline: {metrics['policy_agreement']:.2%} "
              f"({metrics['agreed_cases']}/{metrics['evaluated_cases']})")
        for row in metrics["rows"]:
            print(f"  {row['case']:<8} rl={row['rl_behavior']:<10} baseline={row['baseline_behavior']:<10} "
                  f"{'AGREE' if row['agree'] else 'DIFF'}")
        print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())