from typing import Dict, Tuple

try:
    import torch
    import torch.nn as nn
except ImportError:  # pragma: no cover - exercise requires torch
    torch = None
    nn = None

# Behavior classes match the deterministic rule-based baseline (Faza 5 experiment).
BEHAVIORS: Dict[int, str] = {0: "normal", 1: "frontflip", 2: "backflip", 3: "face_user"}


class FlyWireBrainRL(nn.Module if nn is not None else object):
    """Offline RL experiment model (isolated from the production request path).

    Ported from the fly-whatsapp-project prototype. Kept inside training/ so the
    stdlib-only inference engine (connectome.server) never depends on torch.
    """

    def __init__(self, in_features: int = 6, hidden: int = 128, out_states: int = 4):
        if nn is None:
            raise ImportError(
                "torch is required for RL experiments. Install it or run from the "
                "python_brain venv that ships with the reference project."
            )
        super().__init__()
        self.optic_lobe = nn.Linear(in_features, 64)
        self.central_complex = nn.Linear(64, hidden)
        self.motor_output = nn.Linear(hidden, 2)
        self.behavior_head = nn.Linear(hidden, out_states)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.optic_lobe(x))
        h = self.relu(self.central_complex(x))
        return self.motor_output(h), self.behavior_head(h)


def type_code_of(msg_type: str) -> float:
    if msg_type in ("image", "video"):
        return 1.0
    if msg_type in ("ptt", "audio"):
        return 2.0
    if msg_type == "sticker":
        return 3.0
    return 0.0


def baseline_behavior(type_code: float) -> int:
    """Deterministic rule-based baseline the RL policy is compared against."""
    if type_code == 1.0:
        return 1
    if type_code == 3.0:
        return 2
    return 3


def sample_goal_for_type(type_code: float, text_len: int, cur_x: float, cur_y: float) -> Tuple[float, float]:
    import math

    radius = 0.45 if type_code == 1.0 else (0.30 if type_code == 2.0 else 0.15)
    angle = type_code * 1.7 + text_len * 0.05 + 1.3
    gx = max(0.02, min(0.98, cur_x + radius * math.cos(angle)))
    gy = max(0.02, min(0.98, cur_y + radius * math.sin(angle)))
    return gx, gy