"""Platform-independent BrainService — the stable application-service boundary.

Phase 8 Slice 1. This is the FIRST stable entry point above the Core Brain
modules: callers coordinate the Brain through typed Python methods instead of
touching internal module structure. It stays completely platform-independent:
no UI, no HTTP/WebSocket, no device/PC/mobile assumptions — signals flow out
only through the :class:`~core.brain_events.sink.EventSink` port.

Responsibilities

- coordinate the existing ingestion, memory, understanding, context, people,
  reasoning, action planning, learning and developer-event modules;
- route every real state transition into an emitted Brain event on the sink
  (memory.created, preference.updated, learning.signal.detected,
  decision.created, action.proposed, plus the unchanged developer.* events);
- preserve user_id + correlation_id end to end and enforce user isolation.

Nothing here executes external actions.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from contracts.brain_events.events import BrainEvent
from contracts.common.ids import UserId
from contracts.common.types import Source
from contracts.feedback.feedback import Feedback
from contracts.memory.memory import Memory, MemoryType
from core.brain_events import DevModePipeline, DevOutcome
from core.brain_events.dispatch import BrainEventDispatcher
from core.brain_events.emitter import BrainEventEmitter
from core.brain_events.sink import CollectingEventSink, EventSink, NullEventSink
from core.context import Context, ContextEngine
from core.context.personalization import (
    ContextFact,
    PersonalContext,
    PersonalContextBuilder,
    personal_system_prompt,
    personalized_user_prompt,
)
from core.context.models import ScoredMemory, SearchQuery
from core.context.ports import SemanticSearch
from core.context.search import LexicalSemanticSearch
from core.observability import get_logger
from core.ingestion import (
    IngestionOutcome,
    IngestionResult,
    IngestionService,
    SqliteEventReceiptRepository,
)
from core.ingestion.transaction import SqliteTransaction
from core.learning import (
    AssistanceProfile,
    LearningEngine,
    LearningStatus,
    SqliteLearningStateRepository,
    StoredFeedback,
)
from core.memory import MemoryService, SqliteMemoryRepository
from core.people import (
    PeopleError,
    PeopleIntelligence,
    PeopleSummary,
    PersonResolution,
    PersonTimeline,
    Preference,
)
from core.learning.candidates import (
    PersonalizedAnswer,
    RecordedCandidate,
    answer_instruction,
    route_candidates,
)
from core.learning.exceptions import LearningValidationError
from core.people.exceptions import PeopleValidationError
from core.people.models import DeveloperPreferences, PreferenceDomain
from core.reasoning import ReasoningResult
from core.reasoning.context import ContextDistillationLimits, build_reasoning_context
from core.reasoning.models import ReasoningContext
from core.understanding.exceptions import LLMGatewayError
from core.understanding import (
    DeveloperContext,
    GatewayConfig,
    LLMGateway,
    build_gateway,
)

from .exceptions import (
    BrainServiceConfigurationError,
    BrainServiceValidationError,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _event_source_kwargs(source: Source | None) -> dict[str, Source]:
    return {"source": source} if source is not None else {}


_T = TypeVar("_T")


def _as_service_validation(operation: Callable[[], _T]) -> _T:
    """Translate a Core module's input error into a public validation error.

    People and Learning own the detailed rules (bounded non-empty ids, known
    domains, usable names). Those errors mean "the caller sent something the
    Brain cannot use", which is ``validation_error`` at the API boundary — never
    an opaque ``internal_error``. Non-validation failures are left untouched.
    """
    try:
        return operation()
    except (PeopleValidationError, LearningValidationError) as exc:
        raise BrainServiceValidationError(str(exc), cause=exc) from exc


class PersonalInsight(BaseModel):
    """A personalized answer plus how the Brain arrived at it.

    Provider-agnostic on purpose: which provider ran is reported as data, and
    no provider-specific type escapes into Core.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    question: str
    answer: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    used_context: bool = False
    missing_context: list[str] = Field(default_factory=list, max_length=16)
    provider: str
    fallback_used: bool = False
    context_fact_count: int = Field(default=0, ge=0)
    #: The memories the answer was grounded in. Empty when the Brain had
    #: nothing to answer from, which is the honest signal that an answer is
    #: ungrounded rather than merely short.
    grounding: list[ContextFact] = Field(default_factory=list, max_length=32)
    recorded_candidates: list[RecordedCandidate] = Field(default_factory=list)


def _context_only_answer(context: PersonalContext) -> PersonalizedAnswer:
    """Deterministic answer used when no provider could be used.

    Honest by construction: it reports only what the Brain already stored for
    this user and says the model was not consulted. It never invents a fact.
    """
    if context.is_empty:
        return PersonalizedAnswer(
            answer=(
                "I have no stored context for this request, and no language "
                "model was available to reason over it."
            ),
            confidence=0.0,
            used_context=False,
            missing_context=["stored user context"],
        )
    lines = ["From your own stored context:"]
    for fact in (
        context.preferences + context.memories + context.people + context.learned
    ):
        lines.append(f"- [{fact.source}] {fact.text}")
    return PersonalizedAnswer(
        answer=(
            "\n".join(lines)
            + "\n\n(no language model was available; this is your stored "
            "context only)"
        ),
        confidence=0.3,
        used_context=True,
    )


class ChatOutcome(BaseModel):
    """One conversational turn: the answer plus how it can be trusted.

    Mirrors what the API puts on the wire, but provider-agnostic and free of
    wire concerns so the Python caller gets the same guarantees as an HTTP one.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    message: str
    answer: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provider: str
    fallback_used: bool = False
    session_id: str | None = None
    grounding: list[ContextFact] = Field(default_factory=list, max_length=32)
    context_fact_count: int = Field(default=0, ge=0)
    missing_context: list[str] = Field(default_factory=list, max_length=16)
    learning_recorded: int = Field(default=0, ge=0)
    correlation_id: str | None = None


#: Placeholder anchor for a turn the caller did not tie to a real event. It is
#: only ever passed when learning is switched off, so nothing can be written
#: against it; a real id always replaces it.
_UNANCHORED_TURN_ID = "chat:unanchored-turn"


_log = get_logger("service")


class BrainService:
    """Typed application-service boundary over the Core Brain modules."""

    def __init__(
        self,
        *,
        memory: MemoryService | None = None,
        ingestion: IngestionService | None = None,
        understanding: LLMGateway | None = None,
        context: ContextEngine | None = None,
        search: SemanticSearch | None = None,
        people: PeopleIntelligence | None = None,
        learning: LearningEngine | None = None,
        pipeline: DevModePipeline | None = None,
        emitter: BrainEventEmitter | None = None,
        sink: EventSink | None = None,
        dispatcher: BrainEventDispatcher | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if memory is not None and not isinstance(memory, MemoryService):
            raise TypeError("memory must be a MemoryService")
        if ingestion is not None and not isinstance(ingestion, IngestionService):
            raise TypeError("ingestion must be an IngestionService")
        if context is not None and not isinstance(context, ContextEngine):
            raise TypeError("context must be a ContextEngine")
        if people is not None and not isinstance(people, PeopleIntelligence):
            raise TypeError("people must be a PeopleIntelligence")
        if learning is not None and not isinstance(learning, LearningEngine):
            raise TypeError("learning must be a LearningEngine")

        self._memory = memory
        self._ingestion = ingestion
        self._understanding = understanding
        self._context = context
        # The retrieval port is kept on the service so `search` and `chat` can
        # read memory without going through a transport or a UI. When a host
        # injects one, it is reused rather than second-guessed.
        self._search = search
        self._people = people
        self._learning = learning
        self._now = now or _utcnow

        self._sink = sink if sink is not None else NullEventSink()
        if not hasattr(self._sink, "emit") or not callable(self._sink.emit):
            raise TypeError("sink must implement EventSink.emit(event)")
        self._emitter = emitter or BrainEventEmitter()
        self._dispatcher = dispatcher or BrainEventDispatcher(
            self._emitter, self._sink
        )
        if self._dispatcher.sink is not self._sink:
            # The service owns egress: a custom dispatcher must target our sink.
            self._dispatcher = BrainEventDispatcher(self._emitter, self._sink)

        self._pipeline = pipeline or DevModePipeline(
            emitter=self._emitter, sink=self._sink
        )
        self._pipeline.sink = self._sink
        self._pipeline.learning = self._learning

    # -- debug surface ---------------------------------------------------------
    @property
    def sink(self) -> EventSink:
        return self._sink

    @property
    def emitted(self) -> list[BrainEvent]:
        """Events captured by the attached sink (empty for NullEventSink)."""
        if isinstance(self._sink, CollectingEventSink):
            return self._sink.emitted
        return []

    # -- ingest: real transition -> memory.created -----------------------------
    def ingest(
        self,
        data: Mapping[str, Any],
        *,
        correlation_id: str | None = None,
        event_source: Source | None = None,
    ) -> IngestionResult:
        """Ingest a source event; emit memory.created per new memory.

        When the event names its subject but carries no ``person_id``, the
        identity is resolved here — deterministically, without merging — so the
        produced memory is linked to a real person and the name becomes
        searchable. An ambiguous name links nothing: the event is still ingested,
        it just stays unattached to a person.

        Duplicate events are receipted and produce NO memories, hence NO
        duplicate events (idempotency preserved).
        """
        if self._ingestion is None:
            raise BrainServiceConfigurationError("ingestion not configured")
        if not isinstance(data, Mapping):
            raise BrainServiceValidationError("ingest expects a source-event mapping")
        if correlation_id is not None:
            data = dict(data)
            data["correlation_id"] = correlation_id

        data, _ = self._resolve_subject_person(
            data, correlation_id=correlation_id, event_source=event_source
        )
        _log.info(
            "event.received",
            event_id=data.get("id"),
            event_type=data.get("type"),
            subject_present=bool(data.get("subject")),
            correlation_id=correlation_id,
        )
        result = self._ingestion.ingest(data)
        if result.outcome == IngestionOutcome.ACCEPTED and self._memory is not None:
            for memory_id in result.memory_ids:
                memory = self._get_memory_safe(result.user_id, memory_id)
                if memory is not None:
                    self._dispatcher.memory_created(
                        memory,
                        correlation_id=result.correlation_id,
                        **_event_source_kwargs(event_source),
                    )
        # The outcome is the whole story of an ingest, so it is logged at a
        # level that matches its severity: a rejection is a warning, never an
        # error, because the request itself was handled correctly.
        if result.outcome == IngestionOutcome.ACCEPTED:
            _log.info(
                "ingest.accepted",
                event_id=result.event_id,
                user_id=result.user_id,
                correlation_id=result.correlation_id,
                memory_count=len(result.memory_ids),
            )
        elif result.outcome == IngestionOutcome.DUPLICATE:
            _log.info(
                "ingest.duplicate",
                event_id=result.event_id,
                user_id=result.user_id,
                duplicate_of=result.duplicate_of_event_id,
            )
        else:
            _log.warning(
                "ingest.rejected",
                event_id=result.event_id,
                user_id=result.user_id,
                reason=result.reason,
            )
        return result

    def _resolve_subject_person(
        self,
        data: Mapping[str, Any],
        *,
        correlation_id: str | None,
        event_source: Source | None,
    ) -> tuple[Mapping[str, Any], PersonResolution | None]:
        """Attach a resolved ``person_id`` to a named-but-unidentified subject."""
        if self._people is None:
            return data, None
        subject = data.get("subject")
        if not isinstance(subject, Mapping):
            return data, None
        if subject.get("person_id"):
            return data, None
        name = subject.get("person_name")
        if not isinstance(name, str) or not name.strip():
            return data, None
        user_id = data.get("user_id")
        if not isinstance(user_id, str) or not user_id:
            return data, None
        try:
            resolution = self.resolve_person(
                UserId(user_id),
                name,
                correlation_id=correlation_id,
                event_source=event_source,
            )
        except (BrainServiceValidationError, PeopleError):
            return data, None
        if resolution.person_id is None:
            return data, resolution
        updated = dict(data)
        updated["subject"] = {**subject, "person_id": resolution.person_id}
        return updated, resolution

    def _get_memory_safe(
        self, user_id: UserId, memory_id: str
    ) -> Memory | None:
        try:
            return self._memory.get_memory(user_id, memory_id)
        except Exception:
            return None

    # -- learning: real transition -> learning.signal.detected + preference ---- 
    def record_feedback(
        self,
        feedback: Feedback,
        *,
        correlation_id: str | None = None,
        event_source: Source | None = None,
    ) -> StoredFeedback:
        """Record feedback; emit learning.signal.detected (+ preference.updated
        for any preference the learning rules newly wrote or changed)."""
        if self._learning is None:
            raise BrainServiceConfigurationError("learning not configured")
        if not isinstance(feedback, Feedback):
            raise BrainServiceValidationError("feedback must be a Feedback contract")

        correlation = (
            correlation_id if correlation_id is not None else feedback.correlation_id
        )
        learning_feedback = feedback
        if feedback.correlation_id != correlation:
            learning_feedback = feedback.model_copy(
                update={"correlation_id": correlation}
            )

        before = self._preference_signatures(learning_feedback.user_id)
        stored = _as_service_validation(
            lambda: self._learning.record_feedback(learning_feedback)
        )

        self._dispatcher.learning_signal_detected(
            stored.signal,
            correlation_id=correlation,
            **_event_source_kwargs(event_source),
        )

        after = self._preference_signatures(feedback.user_id)
        added = after - before
        if added and self._people is not None:
            for preference in self._people.preferences(feedback.user_id):
                if self._signature(preference) in added:
                    self._dispatcher.preference_updated(
                        feedback.user_id,
                        preference,
                        correlation_id=correlation,
                        **_event_source_kwargs(event_source),
                    )
        _log.info(
            "learning.recorded",
            user_id=feedback.user_id,
            signal_kind=stored.signal.kind.value,
            signal_topic=stored.signal.topic,
            signal_strength=stored.signal.strength,
            memory_id=stored.memory_id,
            learned_preference_count=len(added),
            correlation_id=correlation,
        )
        return stored

    def _preference_signatures(self, user_id: UserId) -> set[tuple]:
        if self._people is None:
            return set()
        return {self._signature(pref) for pref in self._people.preferences(user_id)}

    @staticmethod
    def _signature(preference: Preference) -> tuple:
        return (
            preference.domain.value if preference.domain else None,
            preference.name,
            preference.value,
            round(preference.importance, 3),
        )

    # -- people: real transition -> preference.updated ------------------------
    def record_preference(
        self,
        user_id: UserId,
        *,
        name: str,
        value: str,
        domain: PreferenceDomain | None = None,
        confidence: float | None = None,
        importance: float | None = None,
        source: Source | None = None,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        event_source: Source | None = None,
    ) -> Preference:
        """Record a preference; emit preference.updated for the write."""
        if self._people is None:
            raise BrainServiceConfigurationError("people not configured")
        if isinstance(domain, str):
            try:
                domain = PreferenceDomain(domain)
            except ValueError as exc:
                raise BrainServiceValidationError(
                    f"unknown preference domain: {domain!r}", cause=exc
                ) from exc
        preference = _as_service_validation(
            lambda: self._people.record_preference(
                user_id,
                name=name,
                value=value,
                domain=domain,
                confidence=confidence,
                importance=importance,
                source=source,
                metadata=metadata,
            )
        )
        self._dispatcher.preference_updated(
            user_id,
            preference,
            correlation_id=correlation_id,
            **_event_source_kwargs(event_source),
        )
        _log.info(
            "preference.recorded",
            user_id=user_id,
            name=name,
            domain=domain.value if domain is not None else None,
            explicit=True,
            correlation_id=correlation_id,
        )
        return preference

    # -- developer mode: developer.* + decision created/action proposed --------
    def analyze_developer(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
        ask_deploy: bool = False,
        correlation_id: str | None = None,
        event_source: Source | None = None,
    ) -> DevOutcome:
        """Run the Developer Mode pipeline and emit ALL events it implies.

        The normal reasoning flow is: Context (built from the DeveloperContext)
        → Learning Profile (consulted read-only by the engine) → Reasoning →
        Intent/Action Planning → Events. The five developer.* events are
        dispatched by the pipeline; the produced plan also emits
        decision.created + one action.proposed per proposal. Nothing is
        executed.
        """
        if not isinstance(context, DeveloperContext):
            raise BrainServiceValidationError(
                "context must be a DeveloperContext"
            )
        reasoning_context = self._reasoning_context_for(context, task=task)
        outcome = self._pipeline.run(
            context,
            task=task,
            ask_deploy=ask_deploy,
            correlation_id=correlation_id,
            reasoning_context=reasoning_context,
            **_event_source_kwargs(event_source),
        )
        decision_event, action_events = self._dispatcher.emit_plan(
            outcome.plan, **_event_source_kwargs(event_source)
        )
        outcome.events.extend([decision_event, *action_events])
        _log.info(
            "developer.analyzed",
            user_id=outcome.user_id,
            correlation_id=outcome.correlation_id,
            bug_count=len(outcome.reasoning.bugs),
            review_count=len(outcome.reasoning.review_findings),
            proposed_action_count=len(outcome.plan.proposed_actions),
            brain_event_count=len(outcome.events),
        )
        return outcome

    def reason(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
    ) -> ReasoningResult:
        """Context → Learning Profile → Reasoning (no planning, no events).

        A thin read path over the pipeline's ReasoningEngine: builds the
        distilled Context when the Context Engine is configured and consults
        the learning port. Produces no events (no state transition).
        """
        if not isinstance(context, DeveloperContext):
            raise BrainServiceValidationError(
                "context must be a DeveloperContext"
            )
        reasoning_context = self._reasoning_context_for(context, task=task)
        return self._pipeline.reasoning.reason(
            context, task=task, reasoning_context=reasoning_context
        )

    def _reasoning_context_for(
        self,
        context: DeveloperContext,
        *,
        task: str | None = None,
        limits: ContextDistillationLimits | None = None,
    ) -> ReasoningContext | None:
        """Build the distilled ReasoningContext (optional enrichment only)."""
        if self._context is None:
            return None
        try:
            built = self._context.build_context(context, task=task)
            return build_reasoning_context(built, limits=limits)
        except Exception:
            return None

    # -- read surfaces (no events, user-scoped) ---------------------------------
    def understand(
        self,
        corpus: str,
        *,
        user_id: str | None = None,
        corpus_id: str | None = None,
    ):
        if self._understanding is None:
            raise BrainServiceConfigurationError("understanding not configured")
        return self._understanding.understand(
            corpus, user_id=user_id, corpus_id=corpus_id
        )

    def build_context(
        self,
        developer_context: DeveloperContext,
        *,
        task: str | None = None,
    ) -> Context:
        if self._context is None:
            raise BrainServiceConfigurationError("context not configured")
        if not isinstance(developer_context, DeveloperContext):
            raise BrainServiceValidationError(
                "developer_context must be a DeveloperContext"
            )
        return self._context.build_context(developer_context, task=task)

    def preferences(self, user_id: UserId) -> list[Preference]:
        if self._people is None:
            raise BrainServiceConfigurationError("people not configured")
        return _as_service_validation(
            lambda: self._people.preferences(user_id)
        )

    def developer_preferences(self, user_id: UserId) -> DeveloperPreferences:
        if self._people is None:
            raise BrainServiceConfigurationError("people not configured")
        return _as_service_validation(
            lambda: self._people.developer_preferences(user_id)
        )

    def people_summary(self, user_id: UserId) -> PeopleSummary:
        if self._people is None:
            raise BrainServiceConfigurationError("people not configured")
        return _as_service_validation(lambda: self._people.people_summary(user_id))

    def people_timeline(
        self,
        user_id: UserId,
        person_id: str,
        *,
        limit: int | None = None,
    ) -> PersonTimeline:
        if self._people is None:
            raise BrainServiceConfigurationError("people not configured")
        return _as_service_validation(
            lambda: self._people.timeline(user_id, person_id, limit=limit)
        )

    def resolve_person(
        self,
        user_id: UserId,
        name: str,
        *,
        aliases: Sequence[str] = (),
        correlation_id: str | None = None,
        event_source: Source | None = None,
    ) -> PersonResolution:
        """Resolve one person name; emit ``person.created`` only on creation.

        The single emission site for a new identity: an exact match returns the
        existing person, an ambiguous name returns candidates without writing,
        and only a freshly minted id produces an event.
        """
        if self._people is None:
            raise BrainServiceConfigurationError("people not configured")
        resolution = _as_service_validation(
            lambda: self._people.resolve_person(
                user_id, name, aliases=aliases, source=event_source
            )
        )
        if resolution.created and resolution.person_id is not None:
            self._dispatcher.person_created(
                user_id,
                resolution.person_id,
                resolution.name,
                memory_id=resolution.memory_id,
                correlation_id=correlation_id,
                **_event_source_kwargs(event_source),
            )
        # Identity resolution is the one place where "created vs reused vs
        # ambiguous" matters to a reader, so the branch is named explicitly.
        if resolution.ambiguous:
            _log.warning(
                "person.ambiguous",
                user_id=user_id,
                candidate_count=len(resolution.candidates),
                wrote_nothing=True,
                correlation_id=correlation_id,
            )
        else:
            _log.info(
                "person.resolved",
                user_id=user_id,
                person_id=resolution.person_id,
                created=resolution.created,
                correlation_id=correlation_id,
            )
        return resolution

    def learning_status(self, user_id: UserId) -> LearningStatus:
        if self._learning is None:
            raise BrainServiceConfigurationError("learning not configured")
        return _as_service_validation(lambda: self._learning.learning_status(user_id))

    def feedback_history(
        self, user_id: UserId, *, limit: int | None = None
    ) -> list[StoredFeedback]:
        if self._learning is None:
            raise BrainServiceConfigurationError("learning not configured")
        return _as_service_validation(
            lambda: self._learning.feedback_history(user_id, limit=limit)
        )

    def personalization_profile(self, user_id: UserId) -> AssistanceProfile:
        if self._learning is None:
            raise BrainServiceConfigurationError("learning not configured")
        return _as_service_validation(
            lambda: self._learning.personalization_profile(user_id)
        )

    # -- personalized reasoning (provider-agnostic) --------------------------
    def personalized_insight(
        self,
        user_id: UserId,
        question: str,
        *,
        target_event_id: str,
        correlation_id: str | None = None,
        record_learning: bool = True,
    ) -> PersonalInsight:
        """Answer a question with bounded Brain context, via the LLM gateway.

        The order is fixed and Brain-owned:

        1. assemble relevant, user-scoped context (memories, preferences,
           mentioned people, learned evidence);
        2. ask the configured provider for a **structured** answer;
        3. validate it through the gateway (unvalidated text never returns);
        4. route only evidence-backed learning candidates into the existing
           Learning Engine — a model answer is never stored as a fact;
        5. on provider failure, answer deterministically from the user's own
           stored context instead of failing.

        ``target_event_id`` anchors any learning to a real interaction; the
        Brain never invents a traceability id.
        """
        if self._understanding is None:
            raise BrainServiceConfigurationError("understanding not configured")
        if self._context is None:
            raise BrainServiceConfigurationError("context not configured")
        if not (question or "").strip():
            raise BrainServiceValidationError("question must be non-empty")
        if not (target_event_id or "").strip():
            raise BrainServiceValidationError("target_event_id is required")
        if not isinstance(self._understanding, LLMGateway):
            raise TypeError("understanding must be an LLMGateway")
        if self._memory is None:
            raise BrainServiceConfigurationError("memory not configured")

        context = self._personal_context_builder().build(user_id, question)

        provider_name = self._understanding.provider.name
        fallback_used = False
        missing: list[str] = []
        try:
            answer = self._understanding.generate_structured(
                PersonalizedAnswer,
                system=personal_system_prompt(),
                user=personalized_user_prompt(
                    context, instruction=answer_instruction()
                ),
            )
        except LLMGatewayError:
            # Deterministic, honest fallback: report what the Brain itself
            # knows, and that no model was used at all.
            answer = _context_only_answer(context)
            provider_name = "context-only"
            fallback_used = True

        recorded: list[RecordedCandidate] = []
        if record_learning and self._learning is not None:
            recorded = route_candidates(
                list(answer.candidates),
                user_id=user_id,
                target_event_id=target_event_id,
                correlation_id=correlation_id,
                record=self._learning.record_feedback,
                record_preference=(
                    self._people.record_preference if self._people is not None else None
                ),
            )

        _log.info(
            "insight.answered",
            user_id=user_id,
            provider=provider_name,
            fallback_used=fallback_used,
            confidence=answer.confidence,
            context_fact_count=(
                len(context.memories)
                + len(context.preferences)
                + len(context.people)
                + len(context.learned)
            ),
            missing_context_count=len(missing or list(answer.missing_context)),
            recorded_candidate_count=len(recorded),
            correlation_id=correlation_id,
        )
        return PersonalInsight(
            user_id=user_id,
            question=context.request,
            answer=answer.answer,
            confidence=answer.confidence,
            used_context=answer.used_context,
            missing_context=missing or list(answer.missing_context),
            provider=provider_name,
            fallback_used=fallback_used,
            context_fact_count=(
                len(context.memories)
                + len(context.preferences)
                + len(context.people)
                + len(context.learned)
            ),
            grounding=list(context.memories),
            recorded_candidates=recorded,
        )

    # -- retrieval and conversation ------------------------------------------
    def search(
        self,
        user_id: UserId,
        *,
        text: str = "",
        keywords: Sequence[str] = (),
        memory_type: MemoryType | None = None,
        person_id: str | None = None,
        importance_min: float | None = None,
        limit: int = 10,
        correlation_id: str | None = None,
    ) -> list[ScoredMemory]:
        """Rank this user's memories for a question. Deterministic, user-scoped.

        The Brain owned retrieval all along; this is the service-level door onto
        it. ``user_id`` is mandatory and is passed straight into the query, so
        isolation is a property of the call rather than a filter a caller could
        forget. An empty query with no filters is a legitimate listing by rank.
        """
        if self._memory is None:
            raise BrainServiceConfigurationError("memory not configured")
        if limit < 1:
            raise BrainServiceValidationError("limit must be >= 1")
        query_text = (text or "").strip()
        keyword_list = [str(k) for k in keywords if str(k).strip()]

        if not query_text and not keyword_list:
            # A query-less call is a listing, not a search. The lexical ranker
            # legitimately returns nothing when it has no terms to match, so
            # listing goes through the Memory Engine's own importance/recency
            # ordering instead of asking the ranker to rank an empty question.
            _log.info(
                "search.listing",
                user_id=user_id,
                limit=limit,
                correlation_id=correlation_id,
            )
            listed = self._memory.retrieve_relevant_memories(
                user_id,
                memory_type=memory_type,
                person_id=person_id,
                importance_min=importance_min,
                limit=limit,
            )
            _log.info(
                "search.completed",
                user_id=user_id,
                has_query=False,
                returned=len(listed),
                limit=limit,
                correlation_id=correlation_id,
            )
            return [ScoredMemory(memory=item, score=item.importance) for item in listed]

        query = SearchQuery(
            user_id=user_id,
            text=query_text,
            keywords=keyword_list,
            top_k=limit,
        )
        results = self._search_port().search(query)
        if memory_type is not None:
            results = [r for r in results if r.memory.type == memory_type]
        if person_id is not None:
            results = [r for r in results if person_id in r.memory.related_people]
        if importance_min is not None:
            results = [r for r in results if r.memory.importance >= importance_min]
        _log.info(
            "search.completed",
            user_id=user_id,
            has_query=bool(query_text or keywords),
            returned=len(results),
            limit=limit,
            correlation_id=correlation_id,
        )
        return results

    def chat(
        self,
        user_id: UserId,
        message: str,
        *,
        session_id: str | None = None,
        limit: int = 8,
        target_event_id: str | None = None,
        record_learning: bool = True,
        correlation_id: str | None = None,
    ) -> ChatOutcome:
        """Answer one question from this user's own Brain state.

        Delegates to :meth:`personalized_insight` so the conversational path and
        the programmatic path cannot drift apart, and adds the two things a
        caller needs to trust the answer: which memories it rests on, and
        whether learning happened.

        Learning is only recorded when ``target_event_id`` is supplied. The Brain
        never invents a traceability id, so an unanchored turn answers without
        writing, and says so in the outcome.
        """
        text = (message or "").strip()
        if not text:
            raise BrainServiceValidationError("message must be non-empty")

        anchor = (target_event_id or "").strip() or None
        should_record = bool(record_learning and anchor)
        if record_learning and not anchor:
            _log.info(
                "chat.learning_skipped",
                user_id=user_id,
                session_id=session_id,
                reason="no target_event_id: the Brain does not invent traceability ids",
            )

        insight = self.personalized_insight(
            user_id,
            text,
            target_event_id=anchor or _UNANCHORED_TURN_ID,
            correlation_id=correlation_id,
            record_learning=should_record,
        )
        grounding = list(insight.grounding)[: max(1, limit)]
        _log.info(
            "chat.answered",
            user_id=user_id,
            session_id=session_id,
            provider=insight.provider,
            fallback_used=insight.fallback_used,
            confidence=insight.confidence,
            grounding_count=len(grounding),
            learning_recorded=len(insight.recorded_candidates),
            correlation_id=correlation_id,
        )
        return ChatOutcome(
            user_id=user_id,
            session_id=session_id,
            message=text,
            answer=insight.answer,
            confidence=insight.confidence,
            provider=insight.provider,
            fallback_used=insight.fallback_used,
            grounding=grounding,
            context_fact_count=insight.context_fact_count,
            missing_context=insight.missing_context,
            learning_recorded=len(insight.recorded_candidates),
            correlation_id=correlation_id,
        )

    def _search_port(self) -> SemanticSearch:
        """The retrieval port, built over the Brain's own memory when absent."""
        if self._search is not None:
            return self._search
        if self._memory is None:
            raise BrainServiceConfigurationError("memory not configured")
        self._search = LexicalSemanticSearch(self._memory)
        return self._search

    def _personal_context_builder(self) -> PersonalContextBuilder:
        """Wire the context builder over the Brain's own subsystems."""
        if self._memory is None:
            raise BrainServiceConfigurationError("memory not configured")
        return PersonalContextBuilder(
            LexicalSemanticSearch(self._memory),
            people=self._people,
            learning=self._learning,
        )

    # -- lifecycle ---------------------------------------------------------------
    def close(self) -> None:
        if self._ingestion is not None:
            self._ingestion.close()


def build_brain_service(
    path: str | Path = "data/brain.sqlite3",
    *,
    sink: EventSink | None = None,
    provider: str = "heuristic",
) -> BrainService:
    """Wire a ready-to-use BrainService over one SQLite file (or ``:memory:``).

    Co-locates memory, ingestion receipts and learning state on a single shared
    connection so events and state stay consistent. No UI/transport involved.
    """
    db_path = str(path)
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    memory_repo = SqliteMemoryRepository(connection=conn, auto_commit=False)
    receipt_repo = SqliteEventReceiptRepository(connection=conn, auto_commit=False)
    memory = MemoryService(memory_repo)

    ingestion = IngestionService(
        memory,
        receipt_repo,
        transaction=SqliteTransaction(conn),
        finalizer=conn.close,
    )
    people = PeopleIntelligence(memory, writer=memory)
    learning = LearningEngine(
        memory,
        writer=memory,
        state=SqliteLearningStateRepository(
            connection=conn, auto_commit=False
        ),
        people=people,
    )
    gateway = build_gateway(
        GatewayConfig(provider=provider, fallback_provider="heuristic")
    )
    search = LexicalSemanticSearch(memory)
    context = ContextEngine(search, understanding=gateway)

    return BrainService(
        memory=memory,
        ingestion=ingestion,
        understanding=gateway,
        context=context,
        people=people,
        learning=learning,
        emitter=BrainEventEmitter(),
        sink=sink if sink is not None else CollectingEventSink(),
    )