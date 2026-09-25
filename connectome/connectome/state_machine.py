from dataclasses import dataclass, field
from typing import Dict, List, Optional

states = {
    "IDLE": {
        "priority": 0,
        "duration_ms": 0,
        "animation": "hover",
        "movement": "none",
        "speed": 0.1,
        "position": "corner",
        "scale": 1.0,
        "visibility": "dim",
        "sound": None,
        "requires_ack": False,
    },
    "BACKGROUND": {
        "priority": 1,
        "duration_ms": 3000,
        "animation": "drift",
        "movement": "slow",
        "speed": 0.2,
        "position": "corner",
        "scale": 0.8,
        "visibility": "low",
        "sound": None,
        "requires_ack": False,
    },
    "ATTENTION": {
        "priority": 2,
        "duration_ms": 2500,
        "animation": "perk",
        "movement": "toward_center",
        "speed": 0.5,
        "position": "center_left",
        "scale": 1.2,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "CURIOUS": {
        "priority": 3,
        "duration_ms": 3000,
        "animation": "tilt",
        "movement": "circle",
        "speed": 0.4,
        "position": "center",
        "scale": 1.1,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "LISTENING": {
        "priority": 3,
        "duration_ms": 4000,
        "animation": "hover_tilt",
        "movement": "subtle",
        "speed": 0.3,
        "position": "bottom_center",
        "scale": 1.1,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "THINKING": {
        "priority": 4,
        "duration_ms": 4000,
        "animation": "stutter",
        "movement": "minimal",
        "speed": 0.2,
        "position": "center",
        "scale": 1.0,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "TAKEOFF": {
        "priority": 4,
        "duration_ms": 1200,
        "animation": "lift_off",
        "movement": "rise",
        "speed": 0.7,
        "position": "center_upper",
        "scale": 1.2,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "FLYING": {
        "priority": 5,
        "duration_ms": 3000,
        "animation": "fly_circle",
        "movement": "figure_eight",
        "speed": 0.9,
        "position": "center",
        "scale": 1.1,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "LANDING": {
        "priority": 1,
        "duration_ms": 1200,
        "animation": "swoop",
        "movement": "descend",
        "speed": 0.5,
        "position": "corner_low",
        "scale": 0.9,
        "visibility": "dim",
        "sound": None,
        "requires_ack": False,
    },
    "PROCESSING": {
        "priority": 5,
        "duration_ms": 3500,
        "animation": "spin",
        "movement": "orbiting",
        "speed": 0.6,
        "position": "center",
        "scale": 1.0,
        "visibility": "normal",
        "sound": None,
        "requires_ack": False,
    },
    "LEARNING": {
        "priority": 6,
        "duration_ms": 5000,
        "animation": "pulse",
        "movement": "slow_orbit",
        "speed": 0.5,
        "position": "center_upper",
        "scale": 1.2,
        "visibility": "bright",
        "sound": None,
        "requires_ack": False,
    },
    "IMPORTANT": {
        "priority": 7,
        "duration_ms": 8000,
        "animation": "zoom_alert",
        "movement": "toward_user",
        "speed": 0.9,
        "position": "attention_area",
        "scale": 1.5,
        "visibility": "bright",
        "sound": "soft_chime",
        "requires_ack": True,
    },
    "WAITING": {
        "priority": 6,
        "duration_ms": 0,
        "animation": "pacing",
        "movement": "sway",
        "speed": 0.3,
        "position": "bottom_center",
        "scale": 1.0,
        "visibility": "normal",
        "sound": None,
        "requires_ack": True,
    },
    "SUCCESS": {
        "priority": 7,
        "duration_ms": 2500,
        "animation": "happy_bounce",
        "movement": "bounce",
        "speed": 0.7,
        "position": "center",
        "scale": 1.2,
        "visibility": "bright",
        "sound": "success",
        "requires_ack": False,
    },
    "WARNING": {
        "priority": 8,
        "duration_ms": 5000,
        "animation": "shake",
        "movement": "agitated",
        "speed": 1.2,
        "position": "attention_area",
        "scale": 1.3,
        "visibility": "bright",
        "sound": "chime",
        "requires_ack": False,
    },
    "ERROR": {
        "priority": 9,
        "duration_ms": 4000,
        "animation": "falter",
        "movement": "stumble",
        "speed": 0.8,
        "position": "center",
        "scale": 1.0,
        "visibility": "normal",
        "sound": "error",
        "requires_ack": False,
    },
    "SLEEPING": {
        "priority": -1,
        "duration_ms": 0,
        "animation": "slow_pulse",
        "movement": "landed",
        "speed": 0.05,
        "position": "corner",
        "scale": 0.7,
        "visibility": "dim",
        "sound": None,
        "requires_ack": False,
    },
}

_TRANSITIONS = {
    "SLEEPING": {"IDLE", "BACKGROUND", "ATTENTION", "TAKEOFF"},
    "BACKGROUND": {"IDLE", "ATTENTION", "CURIOUS", "SLEEPING", "TAKEOFF"},
    "ATTENTION": {"IDLE", "CURIOUS", "THINKING", "IMPORTANT", "LISTENING", "SLEEPING", "TAKEOFF"},
    "CURIOUS": {"IDLE", "THINKING", "LISTENING", "IMPORTANT", "ATTENTION", "TAKEOFF"},
    "LISTENING": {"IDLE", "THINKING", "PROCESSING", "IMPORTANT", "LEARNING", "TAKEOFF"},
    "THINKING": {"IDLE", "PROCESSING", "IMPORTANT", "SUCCESS", "WAITING", "TAKEOFF"},
    "PROCESSING": {"IDLE", "IMPORTANT", "SUCCESS", "ERROR", "WAITING", "TAKEOFF"},
    "LEARNING": {"IDLE", "IMPORTANT", "SUCCESS", "TAKEOFF"},
    "IMPORTANT": {"IDLE", "WARNING", "SUCCESS", "ERROR", "WAITING", "FLYING"},
    "WAITING": {"IDLE", "IMPORTANT", "WARNING", "SUCCESS", "FLYING"},
    "WARNING": {"IDLE", "IMPORTANT", "ERROR", "SUCCESS"},
    "SUCCESS": {"IDLE", "ATTENTION", "SLEEPING", "FLYING"},
    "ERROR": {"IDLE", "WARNING"},
    "TAKEOFF": {"FLYING", "LANDING", "IDLE"},
    "FLYING": {"LANDING", "ATTENTION", "IMPORTANT", "SUCCESS", "IDLE"},
    "LANDING": {"IDLE", "BACKGROUND", "SLEEPING", "ATTENTION"},
}

DEFAULT_TRANSITIONS = {name: set(_TRANSITIONS.keys()) for name in states}


@dataclass
class StateMachine:
    current: str = "IDLE"
    history: List[str] = field(default_factory=list)

    @property
    def priority(self) -> int:
        return states.get(self.current, {}).get("priority", 0)

    def allowed_transitions(self, state: str) -> set:
        return _TRANSITIONS.get(state, DEFAULT_TRANSITIONS[state])

    def transition_to(self, next: str) -> Optional[str]:
        if next not in states:
            raise KeyError(f"unknown state {next!r}")
        target_priority = states[next]["priority"]
        if target_priority > self.priority:
            self.history.append(self.current)
            self.current = next
            return next
        if next in self.allowed_transitions(self.current):
            self.history.append(self.current)
            self.current = next
            return next
        return None

    def force(self, state: str) -> str:
        if state not in states:
            raise KeyError(f"unknown state {state!r}")
        self.history.append(self.current)
        self.current = state
        return state