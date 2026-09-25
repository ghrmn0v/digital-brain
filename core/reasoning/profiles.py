"""Learning -> Reasoning distillation (Phase 8 Slice 2).

Turns the read-only :class:`~core.learning.models.AssistanceProfile` (built by
the explicit-rule Learning layer — never fake ML) into the bounded reasoning
input features :class:`~core.reasoning.models.LearningInfluence`. Everything is
copied from the profile: confidence, importance and counters are preserved,
nothing is invented. An absent/blank profile yields ``has_profile=False`` with
empty lists — Reasoning still works.
"""

from __future__ import annotations

from core.learning.models import AssistanceProfile

from .models import LearnedAffinity, LearningInfluence


def build_learning_influence(profile: AssistanceProfile) -> LearningInfluence:
    """Distill a learned profile into reasoning input (deterministic copy)."""
    if not isinstance(profile, AssistanceProfile):
        from .exceptions import ReasoningValidationError

        raise ReasoningValidationError(
            "profile must be an AssistanceProfile"
        )

    affinities = [
        LearnedAffinity(
            topic=aff.topic,
            direction=aff.direction,
            positive=aff.positive,
            negative=aff.negative,
            positive_rate=aff.positive_rate,
            updated_at=aff.updated_at,
        )
        for aff in (profile.top_affinities + profile.avoid_topics)
    ]

    has_profile = bool(
        profile.explanation_detail is not None
        or profile.top_affinities
        or profile.avoid_topics
        or profile.nudges
        or profile.feedback_count > 0
        or profile.preference_count > 0
    )

    return LearningInfluence(
        user_id=profile.user_id,
        has_profile=has_profile,
        explanation_detail=profile.explanation_detail,
        top_affinities=affinities,
        avoid_topics=[aff.topic for aff in profile.avoid_topics],
        testing_behavior=any(
            nudge.topic == "testing-behavior" for nudge in profile.nudges
        ),
        feedback_count=profile.feedback_count,
        preference_count=profile.preference_count,
        source_memory_ids=sorted(profile.source_memory_ids),
    )