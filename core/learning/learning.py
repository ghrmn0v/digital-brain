"""Learning Engine (Phase 7) — the deterministic feedback loop.

``record_feedback`` turns a Feedback contract into a learning signal, persists
a durable trace as an OBSERVATION memory (visible to future reasoning through
the Memory Engine), updates the bounded aggregated state, and applies ONLY
explicit deterministic learning rules:

- repeated acceptances reinforce the matching developer preference (recorded
  via People Intelligence → Context/Raisonning already reads those);
- repeated rejections of the same topic lower its affinity and record an
  "avoid <topic>" preference once it crosses the evidence threshold;
- an accepted action while tests were green reinforces testing behaviour.

There is NO fake machine learning here: every number is an honest counted
signal with bounded strength.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from contracts.common.ids import UserId
from contracts.common.types import Source
from contracts.feedback.feedback import Feedback
from contracts.memory.memory import MemoryType

from core.memory.candidate import MemoryCandidate
from core.memory.filters import MemoryQuery, MemoryStatusFilter
from core.people.intelligence import PeopleIntelligence

from .exceptions import LearningValidationError
from .interpreter import FeedbackInterpreter
from .models import (
    AssistanceProfile,
    LearningLimits,
    LearningSignal,
    LearningStatus,
    PreferenceEvidence,
    StoredFeedback,
    TopicAffinity,
    _NEGATIVE_KINDS,
    _POSITIVE_KINDS,
)
from .ports import (
    LearnerMemory,
    LearnerMemoryUpdater,
    LearnerMemoryWriter,
    LearningStateRepository,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class LearningEngine:
    """Deterministic feedback → learning → personalization facade."""

    def __init__(
        self,
        memory: LearnerMemory,
        writer: LearnerMemoryWriter,
        state: LearningStateRepository,
        *,
        people: PeopleIntelligence | None = None,
        updater: LearnerMemoryUpdater | None = None,
        interpreter: FeedbackInterpreter | None = None,
        limits: LearningLimits | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(memory, LearnerMemory):
            raise LearningValidationError("memory must implement LearnerMemory")
        if not isinstance(writer, LearnerMemoryWriter):
            raise LearningValidationError("writer must implement LearnerMemoryWriter")
        if not isinstance(state, LearningStateRepository):
            raise LearningValidationError("state must implement LearningStateRepository")
        if people is not None and not isinstance(people, PeopleIntelligence):
            raise LearningValidationError("people must be a PeopleIntelligence")
        self._memory = memory
        self._writer = writer
        self._state = state
        self._people = people
        self._updater = updater
        self._interpreter = interpreter or FeedbackInterpreter()
        self._limits = limits or LearningLimits()
        self._now_fn = now or _now_utc

    # -- public API -----------------------------------------------------------
    def record_feedback(self, feedback: Feedback) -> StoredFeedback:
        """Interpret, persist and learn from one feedback record."""
        if not isinstance(feedback, Feedback):
            raise LearningValidationError("feedback must be a Feedback contract")

        signal = self._interpreter.interpret(feedback)
        now = self._now_fn()
        trace = self._write_trace(feedback, signal, now)

        status = self._state.get_status(feedback.user_id) or LearningStatus(
            user_id=feedback.user_id
        )
        updated = self._apply_signal(status, signal, now)
        self._state.save_status(updated)

        self._learn_preferences(feedback, signal, updated)

        self._adjust_importance(feedback, signal)

        return StoredFeedback(
            user_id=feedback.user_id,
            feedback=feedback,
            signal=signal,
            memory_id=trace.memory_id,
            stored_at=now,
        )

    def feedback_history(
        self,
        user_id: UserId,
        *,
        limit: int | None = None,
    ) -> list[StoredFeedback]:
        """Replay durable feedback traces from the Memory Engine."""
        self._validate_user(user_id)
        wanted = limit if limit is not None else self._limits.max_feedback_history
        memories = self._memory.list_memories(
            MemoryQuery(
                user_id=user_id,
                memory_type=MemoryType.OBSERVATION,
                status=MemoryStatusFilter.ACTIVE,
                source_provider="learning",
                limit=self._limits.feedback_scan_limit,
            )
        )
        traces: list[StoredFeedback] = []
        for memory in memories:
            meta = memory.metadata or {}
            if not meta.get("learning"):
                continue
            try:
                feedback = Feedback(**meta["feedback"])
                signal = LearningSignal(**meta["signal"])
            except (KeyError, TypeError, ValueError):
                continue
            traces.append(
                StoredFeedback(
                    user_id=user_id,
                    feedback=feedback,
                    signal=signal,
                    memory_id=memory.memory_id,
                    stored_at=memory.created_at,
                )
            )
            if len(traces) >= wanted:
                break
        traces.sort(key=lambda item: item.stored_at)
        return traces[:wanted]

    def learning_status(
        self, user_id: UserId, *, create: bool = False
    ) -> LearningStatus:
        """The aggregated learning state of one user (never another's)."""
        self._validate_user(user_id)
        status = self._state.get_status(user_id)
        if status is None and create:
            status = LearningStatus(user_id=user_id)
            self._state.save_status(status)
        return status or LearningStatus(user_id=user_id)

    def personalization_profile(self, user_id: UserId) -> AssistanceProfile:
        """Readable profile combining preferences + feedback for future use."""
        self._validate_user(user_id)
        status = self.learning_status(user_id)
        return self.build_profile(user_id, status)

    # -- internals -------------------------------------------------------------
    def _write_trace(
        self, feedback: Feedback, signal: LearningSignal, now: datetime
    ) -> Memory:
        meta = {
            "learning": True,
            "feedback_id": feedback.feedback_id,
            "signal_kind": signal.kind.value,
            "topic": signal.topic,
            "feedback": feedback.model_dump(mode="json"),
            "signal": signal.model_dump(mode="json"),
        }
        return self._writer.create_memory(
            MemoryCandidate(
                content=self._trace_summary(signal),
                user_id=feedback.user_id,
                type=MemoryType.OBSERVATION,
                source=Source(provider="learning", component="feedback"),
                importance=0.3,
                metadata=meta,
            )
        )

    @staticmethod
    def _trace_summary(signal: LearningSignal) -> str:
        target = (
            f"{signal.target_type}:{signal.target_id}" if signal.target_id else "context"
        )
        topic = signal.topic or "general"
        return f"feedback {signal.kind.value} for {topic} on {target}"

    def _apply_signal(
        self,
        status: LearningStatus,
        signal: LearningSignal,
        now: datetime,
    ) -> LearningStatus:
        counts = dict(status.signal_counts)
        counts[signal.kind.value] = counts.get(signal.kind.value, 0) + 1

        topics = {affinity.topic: affinity for affinity in status.topics}
        if signal.topic:
            affinity = topics.get(signal.topic)
            if affinity is None:
                affinity = TopicAffinity(
                    topic=signal.topic, updated_at=signal.created_at
                )
            total = (
                affinity.positive
                + affinity.negative
                + affinity.ignored
            )
            if signal.kind in _POSITIVE_KINDS:
                affinity = affinity.model_copy(
                    update={"positive": affinity.positive + 1}
                )
            elif signal.kind in _NEGATIVE_KINDS:
                affinity = affinity.model_copy(
                    update={"negative": affinity.negative + 1}
                )
            else:
                affinity = affinity.model_copy(
                    update={"ignored": affinity.ignored + 1}
                )
            affinity = affinity.model_copy(
                update={
                    "delta_importance": round(
                        affinity.delta_importance + signal.delta_importance, 5
                    ),
                    "updated_at": now,
                }
            )
            topics[signal.topic] = affinity

        ordered_topics = sorted(
            topics.values(),
            key=lambda aff: (
                -aff.sample_size,
                -aff.positive_rate if aff.positive_rate is not None else -1.0,
                aff.topic,
            ),
        )[: self._limits.max_state_topics]

        evidence = {item.key: item for item in status.preference_evidence}
        if signal.preference_domain is not None and signal.preference_name:
            key = f"{signal.preference_domain.value}:{signal.preference_name}"
            entry = evidence.get(key) or PreferenceEvidence(
                key=key,
                domain=signal.preference_domain,
                name=signal.preference_name,
                updated_at=signal.created_at,
            )
            positive = entry.positive + (
                1 if signal.kind in _POSITIVE_KINDS else 0
            )
            negative = entry.negative + (
                1 if signal.kind in _NEGATIVE_KINDS else 0
            )
            sample = positive + negative
            weight = round(positive / sample, 3) if sample else 0.0
            evidence[key] = entry.model_copy(
                update={
                    "positive": positive,
                    "negative": negative,
                    "weight": weight,
                    "updated_at": now,
                }
            )

        ordered_evidence = sorted(
            evidence.values(),
            key=lambda entry: (-entry.weight, entry.key),
        )[: self._limits.max_state_preference_evidence]

        return status.model_copy(
            update={
                "signal_counts": counts,
                "topics": ordered_topics,
                "preference_evidence": ordered_evidence,
                "updated_at": now,
            }
        )

    def _learn_preferences(
        self,
        feedback: Feedback,
        signal: LearningSignal,
        status: LearningStatus,
    ) -> None:
        if self._people is None:
            return
        user_id = feedback.user_id
        latest = status.updated_at or self._now_fn()

        # 1) repeated acceptance of a preference hint → preference.
        if signal.preference_domain is not None and signal.preference_name:
            entry = status.evidence(
                f"{signal.preference_domain.value}:{signal.preference_name}"
            )
            if (
                entry is not None
                and entry.positive >= self._limits.min_evidence_for_preference
                and (entry.positive_rate or 0.0)
                >= self._limits.accept_rate_threshold
            ):
                importance = min(
                    0.9,
                    round(0.3 + 0.1 * entry.positive, 3),
                )
                self._people.record_preference(
                    user_id,
                    name=f"{signal.preference_name}",
                    value=signal.preference_value or "preferred",
                    domain=signal.preference_domain,
                    importance=importance,
                    source=Source(provider="learning", component="feedback"),
                    metadata={
                        "learned": True,
                        "evidence": entry.model_dump(mode="json"),
                    },
                )

        # 2) repeated rejections of a topic → "avoid <topic>" preference.
        if signal.topic:
            affinity = status.affinity(signal.topic)
            if (
                affinity is not None
                and affinity.direction == "negative"
                and affinity.sample_size
                >= self._limits.min_evidence_for_avoidance
            ):
                importance = min(
                    0.9,
                    round(0.3 + 0.1 * affinity.sample_size, 3),
                )
                self._people.record_preference(
                    user_id,
                    name=f"avoid:{signal.topic}",
                    value=(
                        f"avoided after {affinity.negative} rejection(s); "
                        f"positive rate {affinity.positive_rate:.2f}"
                    ),
                    importance=importance,
                    source=Source(provider="learning", component="feedback"),
                    metadata={
                        "learned": True,
                        "avoid_topic": signal.topic,
                        "evidence": affinity.model_dump(mode="json"),
                    },
                )

        # 3) accepted while tests were green → reinforce testing preference.
        if (
            signal.tests_were_green is True
            and signal.kind in _POSITIVE_KINDS
        ):
            self._people.record_preference(
                user_id,
                name="fix-accepted-after-tests",
                value="tested fixes are accepted",
                domain=_testing_domain(signal),
                importance=min(0.9, 0.4 + 0.1 * signal.strength),
                source=Source(provider="learning", component="feedback"),
                metadata={"learned": True, "tests_status": "green"},
            )

    def _adjust_importance(
        self, feedback: Feedback, signal: LearningSignal
    ) -> None:
        if self._updater is None or signal.target_type != "memory":
            return
        if signal.target_id is None:
            return
        try:
            memory = self._memory.get_memory(feedback.user_id, signal.target_id)
        except Exception:
            return
        delta = signal.delta_importance
        if delta == 0.0:
            return
        importance = round(
            min(
                self._limits.importance_max,
                max(self._limits.importance_min, memory.importance + delta),
            ),
            3,
        )
        self._updater.update_memory(
            feedback.user_id,
            memory.memory_id,
            importance=importance,
        )

    def build_profile(
        self, user_id: UserId, status: LearningStatus
    ) -> AssistanceProfile:
        """Assemble the readable personalization profile (no storage)."""
        from .personalization import PersonalizationEngine

        return PersonalizationEngine().assistance_profile(
            user_id,
            status=status,
            people=self._people,
            limits=self._limits,
            now=self._now_fn(),
        )

    @staticmethod
    def _validate_user(user_id: UserId) -> None:
        if not user_id or not str(user_id).strip():
            raise LearningValidationError("user_id must be a non-empty string")


def _testing_domain(signal: LearningSignal):
    from core.people.models import PreferenceDomain

    if "test" in (signal.topic or "").lower():
        return PreferenceDomain.TESTING
    return None