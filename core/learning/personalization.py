"""Personalization (Phase 7) — deterministic assistance profile.

Combines Memory-backed developer preferences (People Intelligence) with counted
feedback evidence to produce a readable :class:`AssistanceProfile` a future
reasoning pass (or a client) can act on. All signals are honest counts and
bounded rates — no inferred sensitive data, no fake ML.
"""

from __future__ import annotations

from datetime import datetime

from contracts.common.ids import UserId

from core.people.intelligence import PeopleIntelligence
from core.people.models import Preference

from .models import (
    AssistanceNudge,
    AssistanceProfile,
    LearningLimits,
    LearningStatus,
    TopicAffinity,
)

_EXPLANATION_DETAIL = "explanation_detail"
_CONCISE_KEY = "explanation_detail:explanation"


class PersonalizationEngine:
    """Builds personalization views from preferences + feedback evidence."""

    def assistance_profile(
        self,
        user_id: UserId,
        *,
        status: LearningStatus,
        people: PeopleIntelligence | None = None,
        limits: LearningLimits | None = None,
        now: datetime | None = None,
    ) -> AssistanceProfile:
        limits = limits or LearningLimits()
        generated_at = now or status.updated_at or datetime.now()

        explanation = self._explanation_preference(user_id, status, people, limits)
        top, avoid = self._affinity_views(status, limits)
        nudges = self._nudges(status, explanation)

        return AssistanceProfile(
            user_id=user_id,
            explanation_detail=explanation,
            top_affinities=top,
            avoid_topics=avoid,
            nudges=nudges,
            feedback_count=sum(status.signal_counts.values()),
            preference_count=self._preference_count(status, people),
            source_memory_ids=[],
            generated_at=generated_at,
        )

    # -- components ------------------------------------------------------------
    @staticmethod
    def _explanation_preference(
        user_id: UserId,
        status: LearningStatus,
        people: PeopleIntelligence | None,
        limits: LearningLimits,
    ) -> Preference | None:
        precedence: list[Preference] = []
        if people is not None:
            dev = people.developer_preferences(user_id)
            precedence = list(dev.explanation_detail)
        return precedence[0] if precedence else None

    @staticmethod
    def _affinity_views(
        status: LearningStatus, limits: LearningLimits
    ) -> tuple[list[TopicAffinity], list[TopicAffinity]]:
        positives = [
            aff for aff in status.topics if aff.direction == "positive"
        ]
        negatives = [
            aff for aff in status.topics if aff.direction == "negative"
        ]
        positives.sort(
            key=lambda aff: (
                -(aff.positive_rate or 0.0),
                -aff.sample_size,
                aff.topic,
            )
        )
        negatives.sort(
            key=lambda aff: (
                -(aff.positive_rate or 0.0),
                -aff.sample_size,
            )
        )
        return (
            positives[: limits.max_profile_affinities],
            negatives[: limits.max_profile_affinities],
        )

    def _nudges(
        self,
        status: LearningStatus,
        explanation: Preference | None,
    ) -> list[AssistanceNudge]:
        nudges: list[AssistanceNudge] = []

        concise = self._concise_evidence(status, explanation)
        if concise is not None:
            weight = concise.weight
            strength = round(0.4 + 0.4 * weight, 3)
            nudges.append(
                AssistanceNudge(
                    topic=_CONCISE_KEY,
                    direction="positive",
                    strength=strength,
                    suggestion=(
                        "Prefer concise explanations for this developer "
                        "(repeatedly preferred)."
                    ),
                )
            )

        for affinity in status.topics:
            if affinity.direction != "negative":
                continue
            if affinity.sample_size < 2:
                continue
            strength = round(
                min(0.9, 0.3 + 0.1 * affinity.sample_size), 3
            )
            nudges.append(
                AssistanceNudge(
                    topic=affinity.topic,
                    direction="negative",
                    strength=strength,
                    suggestion=(
                        f"Avoid proposing actions about '{affinity.topic}' — "
                        f"rejected {affinity.negative}/{affinity.sample_size} times "
                        f"(positive rate {affinity.positive_rate:.2f})."
                    ),
                )
            )

        tested = self._tests_green_evidence(status)
        if tested is not None and tested.positive >= 1:
            nudges.append(
                AssistanceNudge(
                    topic="testing-behavior",
                    direction="positive",
                    strength=round(0.5, 3),
                    suggestion=(
                        "The developer accepts fixes when tests are green — "
                        "prefer verified fixes over blind suggestions."
                    ),
                )
            )
        return nudges

    @staticmethod
    def _concise_evidence(
        status: LearningStatus, explanation: Preference | None
    ):
        return status.evidence(_CONCISE_KEY)

    @staticmethod
    def _tests_green_evidence(status: LearningStatus):
        for entry in status.preference_evidence:
            if entry.name == "fix-accepted-after-tests":
                return entry
        return None

    @staticmethod
    def _preference_count(
        status: LearningStatus, people: PeopleIntelligence | None
    ) -> int:
        if people is not None:
            return len(people.preferences(status.user_id))
        return len(status.preference_evidence)