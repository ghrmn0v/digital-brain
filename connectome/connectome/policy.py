from typing import Dict

from connectome.event_processor import Event
from connectome.model import Brain
from connectome.state_machine import states

NATURAL_STATE = {
    "important_message": "IMPORTANT",
    "notification": "ATTENTION",
    "user_message": "LISTENING",
    "task_reminder": "ATTENTION",
    "calendar_event": "IMPORTANT",
    "process_completed": "SUCCESS",
    "process_failed": "ERROR",
    "warning": "WARNING",
    "app_open": "CURIOUS",
    "app_idle": "IDLE",
    "unknown": "IDLE",
}

PATTERNS: Dict[str, Dict[str, float]] = {
    "IDLE": {},
    "BACKGROUND": {"MBON_gamma": -0.3},
    "ATTENTION": {"MBON_beta": 0.4, "MBON_beta2": 0.4},
    "CURIOUS": {"MBON_beta2": 0.7, "MBON_gamma": 0.3},
    "LISTENING": {"MBON_apostrophe": 0.6, "MBON_bpost": 0.4},
    "THINKING": {"MBON_alpha": 0.5, "MBON_beta": 0.3},
    "TAKEOFF": {"MBON_beta": 0.5, "MBON_output": 0.4},
    "FLYING": {"MBON_output": 0.8, "MBON_alpha": 0.4},
    "LANDING": {"MBON_gamma": 0.6, "MBON_bpost": 0.4},
    "PROCESSING": {"MBON_beta": 0.7},
    "LEARNING": {"MBON_gamma": 0.6, "MBON_output": 0.5},
    "IMPORTANT": {"MBON_output": 0.9, "MBON_alpha": 0.5, "MBON_gamma": 0.4},
    "WAITING": {"MBON_bpost": 0.7, "MBON_output": 0.4},
    "SUCCESS": {"MBON_gamma": 0.8, "MBON_output": 0.5},
    "WARNING": {"MBON_apostrophe": 0.8, "MBON_output": 0.6},
    "ERROR": {"MBON_output": 0.7, "MBON_beta": -0.4},
    "SLEEPING": {},
}

PRIORITY_LEVEL = {
    "IDLE": "BACKGROUND",
    "BACKGROUND": "BACKGROUND",
    "ATTENTION": "LOW",
    "CURIOUS": "LOW",
    "LISTENING": "LOW",
    "THINKING": "MEDIUM",
    "TAKEOFF": "MEDIUM",
    "FLYING": "MEDIUM",
    "LANDING": "LOW",
    "PROCESSING": "MEDIUM",
    "LEARNING": "MEDIUM",
    "IMPORTANT": "HIGH",
    "WAITING": "HIGH",
    "SUCCESS": "HIGH",
    "WARNING": "CRITICAL",
    "ERROR": "CRITICAL",
    "SLEEPING": "BACKGROUND",
}

BOOST = 0.35
THRESHOLD = 0.25

FLIGHT_STATES = ("TAKEOFF", "FLYING", "LANDING")

# Celebration flight: with flight mode ON, joyful natural outcomes (SUCCESS /
# CURIOUS / LEARNING) fly instead of just reacting. Which events are joyful is
# still decided by the brain (natural state learned from feedback), so serious
# events (IMPORTANT/ERROR/WARNING) never produce a flight.
FLIGHT_CELEBRATION = {"SUCCESS", "CURIOUS", "LEARNING"}
FLIGHT_MIN_PRIORITY = 0.3


def score_states(brain: Brain) -> Dict[str, float]:
    mbon = brain.mbon_vector()
    scores: Dict[str, float] = {}
    for state, coeffs in PATTERNS.items():
        score = sum(coeff * mbon.get(comp, 0.0) for comp, coeff in coeffs.items())
        if coeffs:
            score /= max(1.0, len(coeffs))
        scores[state] = score
    return scores


def decide(brain: Brain, event: Event, force_natural: bool = False, flight: bool = True) -> Dict:
    natural = NATURAL_STATE.get(event.name, "IDLE")
    scores = score_states(brain)

    if force_natural and event.priority > 0.0:
        state = natural
        confidence = max(scores.values(), default=0.0)
    else:
        candidates = []
        for state, score in scores.items():
            if not flight and state in FLIGHT_STATES:
                continue
            candidate = score
            if state == natural:
                candidate += BOOST
            candidates.append((candidate, state))
        candidates.sort(reverse=True)
        top_score, top_state = candidates[0]
        if top_score < THRESHOLD:
            top_state = "IDLE"
        if top_state == "IDLE" and event.priority >= 0.7 and natural != "IDLE":
            top_state = natural
        state = top_state
        confidence = top_score

    if (
        flight
        and event.priority >= FLIGHT_MIN_PRIORITY
        and natural in FLIGHT_CELEBRATION
    ):
        state = "FLYING"

    return {
        "state": state,
        "priority": PRIORITY_LEVEL.get(state, "LOW"),
        "confidence": round(confidence, 4),
        "scores": {k: round(v, 4) for k, v in scores.items()},
        "natural_state": natural,
    }