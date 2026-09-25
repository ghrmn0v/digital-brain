"""Phase 7: graduated production influence of the learned policy.

The deterministic rule-based baseline (policy.decide) remains the default
behavior. The offline RL policy snapshot (Faza 5) is allowed to influence the
production state decision only when:

  * the operator has not switched influence off (default: off), and
  * the last offline evaluation report allows it (verdict
    ``CANDIDATE_FOR_PRODUCTION``, i.e. the learned policy matches or strictly
    improves reward vs baseline on every compared case), and
  * the incoming event maps to a covered case, and
  * the learned reaction maps to a state that exists in the state machine.

Any failure while reading the learned artifacts falls back to the baseline state.
Production inference never depends on an untested model ("Never replace a working
deterministic baseline with an untested ML model", and the system must always
have a safe fallback behavior). This module is stdlib-only on purpose: it runs
inside the production request path without torch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from connectome.event_processor import Event
from connectome.state_machine import states

_TRAINING_DIR = Path(__file__).parent / "training"
DEFAULT_RL_SNAPSHOT = _TRAINING_DIR / "rl" / "experiments" / "rl_experiment_latest.json"
DEFAULT_EVALUATION = _TRAINING_DIR / "evaluation_reports" / "evaluation_latest.json"

DEFAULT_MODE = os.environ.get("FLY_LEARNED_INFLUENCE", "off").lower()
MODES = ("off", "auto", "on")

# The only verdict under which the learned policy is "safe to influence production".
CANDIDATE_VERDICT = "CANDIDATE_FOR_PRODUCTION"

# Learned reaction labels (rl_brain.BEHAVIORS) -> fly state.
REACTION_TO_STATE: Dict[str, str] = {
    "normal": "IDLE",
    "face_user": "ATTENTION",
    "frontflip": "IMPORTANT",
    "backflip": "WARNING",
}

# WhatsApp media types (WhatsAppEventMapper.normalizeType) that the Faza 5 RL
# experiment scored as separate cases.
COVERED_CASES = ("text", "image", "audio", "sticker", "video")

# Internal event name -> default case when the media type is not available.
EVENT_TO_CASE: Dict[str, str] = {
    "user_message": "text",
    "notification": "image",
}


def resolve_case(event: Event) -> Optional[str]:
    """Pick the RL scenario case for an event, if it maps to a covered one."""
    if event.name == "user_message":
        return "text"
    if event.name == "notification":
        media = (event.context or {}).get("media_type")
        if media in COVERED_CASES:
            return media
        return "image"
    return None


class ProductionInfluence:
    """Safety-gated bridge between the offline learned policy and production."""

    def __init__(
        self,
        mode: Optional[str] = None,
        snapshot_path: Optional[Path] = None,
        evaluation_path: Optional[Path] = None,
    ) -> None:
        self.mode = mode.lower() if mode else DEFAULT_MODE
        if self.mode not in MODES:
            self.mode = "off"
        self.snapshot_path = Path(snapshot_path) if snapshot_path else DEFAULT_RL_SNAPSHOT
        self.evaluation_path = Path(evaluation_path) if evaluation_path else DEFAULT_EVALUATION

    # -- learned artifacts (lazily read, never crash on failure) ------------------

    def verdict(self) -> Optional[str]:
        try:
            data = json.loads(self.evaluation_path.read_text())
            return data.get("verdict")
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def reactions(self) -> Dict[str, str]:
        try:
            data = json.loads(self.snapshot_path.read_text())
            return {row["case"]: row["rl_behavior"] for row in data["evaluation"]["rows"]}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    # -- gate --------------------------------------------------------------------

    def permitted(self, verdict: Optional[str]) -> bool:
        """Whether the learned policy may influence production right now."""
        if self.mode == "off":
            return False
        if self.mode == "on":
            return True
        return verdict == CANDIDATE_VERDICT

    def apply(self, event: Event, state: str) -> tuple[str, Dict[str, Any]]:
        """Return (state, status). Baseline state unless every gate condition holds."""
        verdict = self.verdict()
        status: Dict[str, Any] = {
            "mode": self.mode,
            "verdict": verdict,
            "applied": False,
            "from_state": state,
            "to_state": state,
        }
        if not self.permitted(verdict):
            return state, status

        case = resolve_case(event)
        if case is None:
            return state, status

        reaction = self.reactions().get(case)
        if reaction not in REACTION_TO_STATE:
            return state, status

        learned = REACTION_TO_STATE[reaction]
        if learned not in states or learned == state:
            return state, status

        status.update(
            applied=True,
            from_state=state,
            to_state=learned,
            case=case,
            reaction=reaction,
            source="rl",
        )
        return learned, status

    def summary(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "verdict": self.verdict(),
            "permitted": self.permitted(self.verdict()),
            "covered_cases": sorted(COVERED_CASES),
        }