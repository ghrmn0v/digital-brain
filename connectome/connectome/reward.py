from dataclasses import dataclass

REWARD_MAP = {
    "looked": 0.3,
    "interacted": 0.4,
    "opened_related": 0.5,
    "marked_useful": 1.0,
    "reacted_positive": 0.8,
    "ignored": 0.0,
    "dismissed": -0.5,
    "reacted_negative": -0.9,
    "marked_unnecessary": -1.0,
}


@dataclass
class RewardSignal:
    value: float
    feedback_type: str

    @property
    def is_reward(self) -> bool:
        return self.value > 0

    @property
    def is_punishment(self) -> bool:
        return self.value < 0


def map_feedback(feedback_type: str) -> RewardSignal:
    value = REWARD_MAP.get(feedback_type, 0.0)
    return RewardSignal(value=value, feedback_type=feedback_type)