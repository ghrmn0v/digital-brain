"""BrainApi — the typed, transport-independent client-facing API (Phase 8 S3).

This module only ADAPTS: it maps an :class:`ApiRequest` to the matching
:class:`BrainService` call and wraps the typed result/error in an
:class:`ApiResponse`. It never listens, never parses sockets, never blocks.
The stdio JSON-lines daemon (Slice 3 Part B) and future transports feed raw
messages into :meth:`BrainApi.handle` and stream the returned envelope out.

Design rules enforced here (and by tests):

- only methods/params/results declared in ``contracts.api`` are accepted;
- unsupported versions -> ``VERSION_UNSUPPORTED``, unknown methods ->
  ``UNKNOWN_METHOD``, invalid params -> ``VALIDATION_ERROR``,
  missing capability -> ``NOT_CONFIGURED``, anything else -> ``INTERNAL_ERROR``
  (never a raw exception or stack trace);
- wire shapes are copied/counted from real module results, never invented.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from pydantic import BaseModel, ValidationError

from contracts.api import params as P  # noqa: N812  (wire param models)
from contracts.api import results as R  # noqa: N812  (wire result models)
from contracts.api.envelope import (
    ApiRequest,
    ApiResponse,
    error_response,
    ok_response,
)
from contracts.api.errors import ApiError, ApiErrorCode
from contracts.api.methods import ApiMethod
from contracts.api.registry import (
    API_CONTRACT_VERSION,
    API_METHOD_REGISTRY,
    API_METHOD_SPECS,
    describe_api_methods,
)
from contracts.common.types import Source
from contracts.memory.memory import MemoryType
from core.context.models import ScoredMemory
from core.understanding.developer import (
    DeveloperContext,
    DeveloperFile,
    GitContext,
    TestResultSnapshot,
)

from .brain_service import BrainService
from .exceptions import (
    BrainServiceConfigurationError,
    BrainServiceValidationError,
)

class ApiRequestValidationError(Exception):
    """Raised by the adapter when method params fail their typed model."""


def _bounded_text(value: str, max_length: int = 1900) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _bounded_text_flagged(value: str, max_length: int = 1900) -> tuple[str, bool]:
    """Bound a string and say whether it was cut, for the ``*_truncated`` flags."""
    if not isinstance(value, str):
        return "", False
    if len(value) <= max_length:
        return value, False
    return _bounded_text(value, max_length), True


def _bounded_request_id(value: Any) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return _bounded_text(text, 128)


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors()[:3]:
        location = _bounded_text(
            ".".join(str(part) for part in error.get("loc", ())), 512
        )
        message = _bounded_text(str(error.get("msg", "invalid")), 512)
        parts.append(f"{location}: {message}")
    return _bounded_text("; ".join(parts) or "invalid request")


def _bounded_repr(value: Any, max_length: int = 512) -> str:
    try:
        if isinstance(value, str):
            rendered = repr(
                value if len(value) <= max_length else value[:max_length] + "..."
            )
        elif isinstance(value, (bytes, bytearray)):
            rendered = (
                repr(value)
                if len(value) <= max_length
                else f"<{type(value).__name__} len={len(value)}>"
            )
        elif isinstance(value, (list, tuple, set, dict)):
            rendered = f"<{type(value).__name__} len={len(value)}>"
        elif value is None or isinstance(value, (bool, int, float)):
            rendered = repr(value)
        else:
            rendered = f"<{type(value).__name__}>"
    except Exception:
        rendered = f"<{type(value).__name__}>"
    return _bounded_text(rendered, max_length)


# -- wire mapping helpers (copy, never invent) --------------------------------


def _developer_from_wire(wire: P.DeveloperSnapshotWire) -> DeveloperContext:
    return DeveloperContext(
        version=wire.version,
        user_id=wire.user_id,
        repository=wire.repository,
        root=wire.root,
        files=[
            DeveloperFile(path=file.path, content=file.content, language=file.language)
            for file in wire.files
        ],
        changed_files=list(wire.changed_files),
        current_file=wire.current_file,
        current_line=wire.current_line,
        git_context=(
            GitContext(**wire.git_context.model_dump()) if wire.git_context else None
        ),
        test_results=[
            TestResultSnapshot(**test.model_dump()) for test in wire.test_results
        ],
        user_context=dict(wire.user_context),
    )


def _wire_preference(preference: Any) -> R.PreferenceWire:
    return R.PreferenceWire(
        memory_id=preference.memory_id,
        domain=preference.domain.value if preference.domain else None,
        name=preference.name,
        value=preference.value,
        confidence=preference.confidence,
        importance=preference.importance,
    )


def _wire_reasoning(reasoning: Any) -> R.ReasoningWire:
    intent = reasoning.intent
    tests = reasoning.tests
    return R.ReasoningWire(
        user_id=reasoning.user_id,
        repository=reasoning.repository,
        created_at=reasoning.created_at,
        intent=R.IntentWire(
            intent_kind=intent.intent_kind.value,
            confidence=intent.confidence,
            keywords=list(intent.keywords),
            repository=intent.repository,
            target_file=intent.target_file,
            target_line=intent.target_line,
            fallback_used=intent.fallback_used,
            query=intent.query,
        ),
        bugs=[
            R.BugFindingWire(
                finding_id=bug.finding_id,
                repository=bug.repository,
                file=bug.file,
                line=bug.line,
                column=bug.column,
                title=bug.title,
                message=bug.message,
                severity=bug.severity.value,
                confidence=bug.confidence,
                check=bug.check,
                suggested_fix=bug.suggested_fix,
            )
            for bug in reasoning.bugs
        ],
        review_findings=[
            R.ReviewFindingWire(
                finding_id=finding.finding_id,
                repository=finding.repository,
                file=finding.file,
                line=finding.line,
                category=finding.category.value,
                severity=finding.severity.value,
                explanation=finding.explanation,
                confidence=finding.confidence,
                suggestion=finding.suggestion,
            )
            for finding in reasoning.review_findings
        ],
        tests=R.TestOutcomeWire(
            provided=tests.provided,
            passed=tests.passed,
            failed=tests.failed,
            skipped=tests.skipped,
            errors=tests.errors,
            summary=tests.summary,
            reason=tests.reason,
        ),
        files_scanned=reasoning.files_scanned,
        total_changed=reasoning.total_changed,
        context_used=reasoning.context is not None,
        learning_used=reasoning.learning is not None,
    )


def _wire_plan(plan: Any) -> R.PlanWire:
    return R.PlanWire(
        correlation_id=plan.correlation_id,
        decision=plan.decision,
        proposed_actions=list(plan.proposed_actions),
    )


def _wire_affinity(affinity: Any) -> R.TopicAffinityWire:
    return R.TopicAffinityWire(
        topic=affinity.topic,
        positive=affinity.positive,
        negative=affinity.negative,
        ignored=affinity.ignored,
        positive_rate=affinity.positive_rate,
        direction=affinity.direction,
    )


def _wire_evidence(evidence: Any) -> R.PreferenceEvidenceWire:
    return R.PreferenceEvidenceWire(
        key=evidence.key,
        domain=evidence.domain.value if evidence.domain else None,
        name=evidence.name,
        positive=evidence.positive,
        negative=evidence.negative,
        weight=evidence.weight,
        positive_rate=evidence.positive_rate,
    )


def _event_source_kwargs(source: Source | None) -> dict[str, Any]:
    return {"event_source": source} if source is not None else {}


def _wire_profile(profile: Any) -> R.AssistanceProfileResult:
    return R.AssistanceProfileResult(
        user_id=profile.user_id,
        explanation_detail=(
            _wire_preference(profile.explanation_detail)
            if profile.explanation_detail is not None
            else None
        ),
        top_affinities=[_wire_affinity(aff) for aff in profile.top_affinities],
        avoid_topics=[_wire_affinity(aff) for aff in profile.avoid_topics],
        nudges=[
            R.NudgeWire(
                topic=nudge.topic,
                direction=nudge.direction,
                strength=nudge.strength,
                suggestion=nudge.suggestion,
            )
            for nudge in profile.nudges
        ],
        feedback_count=profile.feedback_count,
        preference_count=profile.preference_count,
        source_memory_ids=list(profile.source_memory_ids),
        generated_at=profile.generated_at,
    )


# -- per-method handlers --------------------------------------------------------


def _handle_ping(
    service: BrainService,
    params: P.PingParams,
    source: Source | None = None,
) -> R.PingResult:
    return R.PingResult()


def _handle_describe(
    service: BrainService,
    params: P.DescribeParams,
    source: Source | None = None,
) -> R.DescribeResult:
    return R.DescribeResult(
        version=API_CONTRACT_VERSION,
        methods=[spec.method.value for spec in API_METHOD_SPECS],
        schemas=describe_api_methods(),
    )


def _handle_ingest(
    service: BrainService,
    params: P.IngestParams,
    source: Source | None = None,
) -> R.IngestionResultWire:
    result = service.ingest(
        params.event.model_dump(),
        correlation_id=params.correlation_id,
        **_event_source_kwargs(source),
    )
    return R.IngestionResultWire(
        outcome=result.outcome.value,
        event_id=result.event_id,
        user_id=result.user_id,
        correlation_id=result.correlation_id,
        memory_ids=list(result.memory_ids),
        reason=result.reason,
        duplicate_of_event_id=result.duplicate_of_event_id,
        events_emitted=len(result.memory_ids) if result.outcome.value == "accepted" else 0,
    )


def _handle_record_feedback(
    service: BrainService,
    params: P.RecordFeedbackParams,
    source: Source | None = None,
) -> R.FeedbackResultWire:
    stored = service.record_feedback(
        params.feedback,
        correlation_id=params.correlation_id,
        **_event_source_kwargs(source),
    )
    signal = stored.signal
    return R.FeedbackResultWire(
        user_id=stored.user_id,
        stored_at=stored.stored_at,
        memory_id=stored.memory_id,
        signal=R.SignalWire(
            kind=signal.kind.value,
            source=signal.source.value,
            topic=signal.topic,
            strength=signal.strength,
            correlation_id=signal.correlation_id,
            preference_domain=(
                signal.preference_domain.value if signal.preference_domain else None
            ),
            preference_name=signal.preference_name,
        ),
    )


def _handle_record_preference(
    service: BrainService,
    params: P.RecordPreferenceParams,
    source: Source | None = None,
) -> R.PreferenceWire:
    preference = service.record_preference(
        params.user_id,
        name=params.name,
        value=params.value,
        domain=params.domain,
        confidence=params.confidence,
        importance=params.importance,
        source=params.source,
        metadata=params.metadata,
        correlation_id=params.correlation_id,
        **_event_source_kwargs(source),
    )
    return _wire_preference(preference)


def _handle_understand(
    service: BrainService,
    params: P.UnderstandParams,
    source: Source | None = None,
) -> R.UnderstandResultWire:
    result = service.understand(
        params.corpus, user_id=params.user_id, corpus_id=params.corpus_id
    )
    return R.UnderstandResultWire(
        version=result.version,
        provider=result.provider,
        fallback_used=result.fallback_used,
        user_id=result.user_id,
        corpus_id=result.corpus_id,
        intent=result.intent.value,
        entities=list(result.entities),
        topics=list(result.topics),
        salience=result.salience,
        confidence=result.confidence,
        summary=result.summary,
        relevant_code_concepts=list(result.relevant_code_concepts),
    )


def _handle_build_context(
    service: BrainService,
    params: P.BuildContextParams,
    source: Source | None = None,
) -> R.ContextResultWire:
    context = service.build_context(
        _developer_from_wire(params.context), task=params.task
    )
    return R.ContextResultWire(
        context_id=context.context_id,
        user_id=context.user_id,
        status=context.status.value,
        repository=context.repository,
        current_file=context.current_file,
        current_task=context.current_task,
        relevant_memory_count=len(context.relevant_memories),
        previous_bug_finding_count=len(context.previous_bug_findings),
        previous_decision_count=len(context.previous_decisions),
        developer_preference_count=len(context.developer_preferences),
        relevant_people_count=len(context.relevant_people),
        fallback_used=context.fallback_used,
    )


def _handle_analyze_developer(
    service: BrainService,
    params: P.AnalyzeDeveloperParams,
    source: Source | None = None,
) -> R.AnalyzeDeveloperResult:
    outcome = service.analyze_developer(
        _developer_from_wire(params.context),
        task=params.task,
        ask_deploy=params.ask_deploy,
        correlation_id=params.correlation_id,
        **_event_source_kwargs(source),
    )
    return R.AnalyzeDeveloperResult(
        user_id=outcome.user_id,
        correlation_id=outcome.correlation_id,
        reasoning=_wire_reasoning(outcome.reasoning),
        plan=_wire_plan(outcome.plan),
        events=list(outcome.events),
    )


def _handle_reason(
    service: BrainService,
    params: P.ReasonParams,
    source: Source | None = None,
) -> R.ReasoningWire:
    result = service.reason(_developer_from_wire(params.context), task=params.task)
    return _wire_reasoning(result)


def _handle_preferences(
    service: BrainService,
    params: P.UserParams,
    source: Source | None = None,
) -> R.PreferencesResult:
    preferences = service.preferences(params.user_id)
    ordered = sorted(preferences, key=lambda preference: (preference_name(preference), preference.memory_id))
    return R.PreferencesResult(
        user_id=params.user_id,
        domains=sorted(
            {p.domain.value for p in preferences if p.domain is not None}
        ),
        preferences=[_wire_preference(preference) for preference in ordered],
    )


def preference_name(preference: Any) -> str:
    return preference.name or ""


def _handle_developer_preferences(
    service: BrainService,
    params: P.UserParams,
    source: Source | None = None,
) -> R.DeveloperPreferencesResult:
    developer = service.developer_preferences(params.user_id)
    return R.DeveloperPreferencesResult(
        user_id=params.user_id,
        languages=[_wire_preference(p) for p in developer.languages],
        coding_style=[_wire_preference(p) for p in developer.coding_style],
        testing=[_wire_preference(p) for p in developer.testing],
        explanation_detail=[_wire_preference(p) for p in developer.explanation_detail],
        commit_style=[_wire_preference(p) for p in developer.commit_style],
        deployment=[_wire_preference(p) for p in developer.deployment],
    )


def _handle_people_summary(
    service: BrainService,
    params: P.UserParams,
    source: Source | None = None,
) -> R.PeopleSummaryResult:
    summary = service.people_summary(params.user_id)
    return R.PeopleSummaryResult(
        user_id=params.user_id,
        people=[
            R.PersonRowWire(
                person_id=person.person_id,
                name=person.name,
                mention_count=person.mention_count,
            )
            for person in summary.people
        ],
    )


def _handle_resolve_person(
    service: BrainService,
    params: P.ResolvePersonParams,
    source: Source | None = None,
) -> R.PersonResolutionWire:
    resolution = service.resolve_person(
        params.user_id,
        params.name,
        aliases=params.aliases,
        correlation_id=params.correlation_id,
        event_source=source,
    )
    return R.PersonResolutionWire(
        user_id=resolution.user_id,
        name=resolution.name,
        person_id=resolution.person_id,
        aliases=list(resolution.aliases),
        created=resolution.created,
        ambiguous=resolution.ambiguous,
        candidates=list(resolution.candidates),
        memory_id=resolution.memory_id,
    )


def _handle_people_timeline(
    service: BrainService,
    params: P.PeopleTimelineParams,
    source: Source | None = None,
) -> R.PeopleTimelineResult:
    timeline = service.people_timeline(
        params.user_id,
        params.person_id,
        limit=params.limit,
    )
    return R.PeopleTimelineResult(
        user_id=timeline.user_id,
        person_id=timeline.person_id,
        entries=[
            R.PersonTimelineEntryWire(
                person_id=entry.person_id,
                memory_id=entry.memory_id,
                memory_type=entry.memory_type.value,
                status=entry.status.value,
                statement=entry.statement,
                statement_truncated=entry.statement_truncated,
                occurred_at=entry.occurred_at,
                created_at=entry.created_at,
                valid_until=entry.valid_until,
                durability=entry.durability.value,
                confidence=entry.confidence,
                importance=entry.importance,
                provenance=R.PersonTimelineSourceWire(
                    provider=entry.provenance.source.provider,
                    component=entry.provenance.source.component,
                    version=entry.provenance.source.version,
                    source_event_id=entry.provenance.source_event_id,
                    correlation_id=entry.provenance.correlation_id,
                    source_event_id_truncated=entry.provenance.source_event_id_truncated,
                    correlation_id_truncated=entry.provenance.correlation_id_truncated,
                    related_event_ids=list(entry.provenance.related_event_ids),
                    evidence=dict(entry.provenance.evidence),
                ),
            )
            for entry in timeline.entries
        ],
        total_entries=timeline.total_entries,
        truncated=timeline.truncated,
        scan_truncated=timeline.scan_truncated,
        person_known=timeline.person_known,
    )


def _handle_learning_status(
    service: BrainService,
    params: P.UserParams,
    source: Source | None = None,
) -> R.LearningStatusResult:
    status = service.learning_status(params.user_id)
    return R.LearningStatusResult(
        user_id=params.user_id,
        signal_counts=dict(status.signal_counts),
        topics=[_wire_affinity(affinity) for affinity in status.topics],
        preference_evidence=[
            _wire_evidence(evidence) for evidence in status.preference_evidence
        ],
    )


def _handle_feedback_history(
    service: BrainService,
    params: P.FeedbackHistoryParams,
    source: Source | None = None,
) -> R.FeedbackHistoryResult:
    items = service.feedback_history(params.user_id, limit=params.limit)
    return R.FeedbackHistoryResult(
        user_id=params.user_id,
        items=[
            R.FeedbackHistoryItemWire(
                stored_at=item.stored_at,
                memory_id=item.memory_id,
                kind=item.signal.kind.value,
                source=item.signal.source.value,
                topic=item.signal.topic,
                strength=item.signal.strength,
                correlation_id=item.signal.correlation_id,
                note=item.signal.note,
            )
            for item in items
        ],
    )


def _handle_personalization_profile(
    service: BrainService,
    params: P.UserParams,
    source: Source | None = None,
) -> R.AssistanceProfileResult:
    return _wire_profile(service.personalization_profile(params.user_id))


# -- retrieval and conversation ---------------------------------------------------


def _memory_hit_wire(scored: ScoredMemory) -> R.MemoryHitWire:
    """Map one ranked memory to the wire, bounding its content."""
    memory = scored.memory
    content, truncated = _bounded_text_flagged(memory.content)
    metadata = memory.metadata if isinstance(memory.metadata, dict) else {}
    correlation = metadata.get("correlation_id")
    return R.MemoryHitWire(
        memory_id=memory.memory_id,
        type=memory.type.value,
        content=content,
        content_truncated=truncated,
        score=scored.score,
        matched_fields=list(scored.matched_fields),
        ranking_reason=scored.ranking_reason,
        confidence=memory.confidence,
        importance=memory.importance,
        status=memory.status.value,
        source_provider=memory.source.provider,
        source_component=memory.source.component,
        created_at=memory.created_at.isoformat(),
        updated_at=memory.updated_at.isoformat(),
        person_ids=[str(pid) for pid in memory.related_people],
        related_event_ids=[str(eid) for eid in memory.related_events],
        correlation_id=correlation if isinstance(correlation, str) else None,
    )


def _handle_search(
    service: BrainService,
    params: P.SearchParams,
    source: Source | None = None,
) -> R.SearchResultWire:
    memory_type = MemoryType(params.memory_type) if params.memory_type else None
    hits = service.search(
        params.user_id,
        text=params.text,
        keywords=params.keywords,
        memory_type=memory_type,
        person_id=params.person_id,
        importance_min=params.importance_min,
        limit=params.limit,
        correlation_id=params.correlation_id,
    )
    return R.SearchResultWire(
        user_id=params.user_id,
        query=params.text,
        items=[_memory_hit_wire(hit) for hit in hits],
        total_returned=len(hits),
        truncated=len(hits) >= params.limit,
        correlation_id=params.correlation_id,
    )


def _handle_chat(
    service: BrainService,
    params: P.ChatParams,
    source: Source | None = None,
) -> R.ChatResultWire:
    outcome = service.chat(
        params.user_id,
        params.message,
        session_id=params.session_id,
        limit=params.limit,
        target_event_id=params.target_event_id,
        record_learning=params.record_learning,
        correlation_id=params.correlation_id,
    )
    grounding: list[R.ChatGroundingWire] = []
    for fact in outcome.grounding:
        if not fact.memory_id:
            continue
        content, truncated = _bounded_text_flagged(fact.text)
        grounding.append(
            R.ChatGroundingWire(
                memory_id=fact.memory_id,
                type=fact.kind,
                content=content,
                content_truncated=truncated,
                score=1.0,
            )
        )
    return R.ChatResultWire(
        user_id=outcome.user_id,
        session_id=outcome.session_id,
        message=outcome.message,
        answer=outcome.answer,
        confidence=outcome.confidence,
        provider=outcome.provider,
        fallback_used=outcome.fallback_used,
        grounded_in=grounding,
        context_fact_count=outcome.context_fact_count,
        missing_context=list(outcome.missing_context),
        learning_recorded=outcome.learning_recorded,
        correlation_id=outcome.correlation_id,
    )


_BrainApiHandler = Callable[
    [BrainService, BaseModel, Source | None],
    BaseModel,
]

_HANDLERS: dict[ApiMethod, _BrainApiHandler] = {
    ApiMethod.PING: _handle_ping,
    ApiMethod.DESCRIBE: _handle_describe,
    ApiMethod.INGEST: _handle_ingest,
    ApiMethod.RECORD_FEEDBACK: _handle_record_feedback,
    ApiMethod.RECORD_PREFERENCE: _handle_record_preference,
    ApiMethod.UNDERSTAND: _handle_understand,
    ApiMethod.BUILD_CONTEXT: _handle_build_context,
    ApiMethod.ANALYZE_DEVELOPER: _handle_analyze_developer,
    ApiMethod.REASON: _handle_reason,
    ApiMethod.PREFERENCES: _handle_preferences,
    ApiMethod.DEVELOPER_PREFERENCES: _handle_developer_preferences,
    ApiMethod.PEOPLE_SUMMARY: _handle_people_summary,
    ApiMethod.PEOPLE_TIMELINE: _handle_people_timeline,
    ApiMethod.LEARNING_STATUS: _handle_learning_status,
    ApiMethod.FEEDBACK_HISTORY: _handle_feedback_history,
    ApiMethod.PERSONALIZATION_PROFILE: _handle_personalization_profile,
    ApiMethod.RESOLVE_PERSON: _handle_resolve_person,
    ApiMethod.SEARCH: _handle_search,
    ApiMethod.CHAT: _handle_chat,
}

_METHOD_VALUES = frozenset(method.value for method in API_METHOD_REGISTRY)


class BrainApi:
    """Typed coordinator between client messages and a BrainService."""

    def __init__(self, service: BrainService) -> None:
        if not isinstance(service, BrainService):
            raise TypeError("BrainApi requires a BrainService")
        self._service = service

    @property
    def service(self) -> BrainService:
        return self._service

    @property
    def methods(self) -> list[str]:
        return [spec.method.value for spec in API_METHOD_SPECS]

    def describe(self) -> R.DescribeResult:
        return _handle_describe(self._service, P.DescribeParams())

    def handle(self, message: Mapping[str, Any]) -> ApiResponse[Any]:
        """Single entry point for any transport: mapping -> validated response."""
        if not isinstance(message, Mapping):
            return error_response(
                "",
                None,
                ApiError(
                    code=ApiErrorCode.BAD_REQUEST,
                    message="request must be a mapping",
                    source="BrainApi",
                ),
            )
        raw_method = message.get("method")
        raw_version = message.get("version", API_CONTRACT_VERSION)
        request_id = _bounded_request_id(message.get("id"))

        if not isinstance(raw_method, str) or raw_method not in _METHOD_VALUES:
            return error_response(
                request_id,
                None,
                ApiError(
                    code=ApiErrorCode.UNKNOWN_METHOD,
                    message=f"unknown method: {_bounded_repr(raw_method)}",
                    source="BrainApi",
                ),
            )
        method = ApiMethod(raw_method)
        if raw_version != API_CONTRACT_VERSION:
            return error_response(
                request_id,
                method,
                ApiError(
                    code=ApiErrorCode.VERSION_UNSUPPORTED,
                    message=(
                        "unsupported contract version: "
                        f"{_bounded_repr(raw_version)}"
                    ),
                    source="BrainApi",
                ),
            )
        try:
            request = ApiRequest.model_validate(dict(message))
        except ValidationError as exc:
            return error_response(
                request_id,
                method,
                ApiError(
                    code=ApiErrorCode.BAD_REQUEST,
                    message=_validation_message(exc),
                    source="BrainApi",
                ),
            )
        return self.respond(request)

    def respond(self, request: ApiRequest) -> ApiResponse[Any]:
        """Dispatch one typed request; every exit path is a typed response."""
        method_spec = API_METHOD_REGISTRY.get(request.method)
        handler = _HANDLERS.get(request.method)
        if method_spec is None or handler is None:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.UNKNOWN_METHOD,
                    message=f"method not implemented: {request.method.value}",
                    source="BrainApi",
                ),
            )
        params_cls = method_spec.params_model
        try:
            params = params_cls.model_validate(request.params)
        except ValidationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.VALIDATION_ERROR,
                    message=_validation_message(exc),
                    source="BrainApi",
                ),
            )

        try:
            result = handler(self._service, params, request.source)
        except ApiRequestValidationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.VALIDATION_ERROR,
                    message=_bounded_text(str(exc)),
                    source="BrainApi",
                ),
            )
        except BrainServiceValidationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.VALIDATION_ERROR,
                    message=_bounded_text(str(exc)),
                    source="BrainService",
                ),
            )
        except BrainServiceConfigurationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.NOT_CONFIGURED,
                    message=_bounded_text(str(exc)),
                    source="BrainService",
                ),
            )
        except Exception as exc:  # nosec B110 — adapter boundary
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.INTERNAL_ERROR,
                    message="internal failure",
                    details={"exception": type(exc).__name__},
                ),
            )
        return ok_response(
            request.id, request.method, result, version=request.version
        )

    def to_json_message(
        self, message: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Transport convenience: handle() then return a JSON-serializable dict."""
        return self.handle(message).model_dump(mode="json")


__all__ = [
    "ApiRequestValidationError",
    "BrainApi",
]