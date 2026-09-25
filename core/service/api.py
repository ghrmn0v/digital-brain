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

_SUPPORTED_VERSION = "v1"


class ApiRequestValidationError(Exception):
    """Raised by the adapter when method params fail their typed model."""


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors()[:3]:
        location = ".".join(str(part) for part in error.get("loc", ()))
        parts.append(f"{location}: {error.get('msg', 'invalid')}")
    return "; ".join(parts) or "invalid request"


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


def _handle_ping(service: BrainService, params: P.PingParams) -> R.PingResult:
    return R.PingResult()


def _handle_describe(service: BrainService, params: P.DescribeParams) -> R.DescribeResult:
    schemas: dict[str, dict[str, Any]] = {}
    for method, (params_cls, result_cls, _) in _SPECS.items():
        schemas[method.value] = {
            "params": params_cls.model_json_schema(),
            "result": result_cls.model_json_schema(),
        }
    return R.DescribeResult(
        version="v1",
        methods=[method.value for method in _SPECS],
        schemas=schemas,
    )


def _handle_ingest(service: BrainService, params: P.IngestParams) -> R.IngestionResultWire:
    result = service.ingest(params.event.model_dump(), correlation_id=params.correlation_id)
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
    service: BrainService, params: P.RecordFeedbackParams
) -> R.FeedbackResultWire:
    stored = service.record_feedback(
        params.feedback, correlation_id=params.correlation_id
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
    service: BrainService, params: P.RecordPreferenceParams
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
    )
    return _wire_preference(preference)


def _handle_understand(
    service: BrainService, params: P.UnderstandParams
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
    service: BrainService, params: P.BuildContextParams
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
    service: BrainService, params: P.AnalyzeDeveloperParams
) -> R.AnalyzeDeveloperResult:
    outcome = service.analyze_developer(
        _developer_from_wire(params.context),
        task=params.task,
        ask_deploy=params.ask_deploy,
        correlation_id=params.correlation_id,
    )
    return R.AnalyzeDeveloperResult(
        user_id=outcome.user_id,
        correlation_id=outcome.correlation_id,
        reasoning=_wire_reasoning(outcome.reasoning),
        plan=_wire_plan(outcome.plan),
        events=list(outcome.events),
    )


def _handle_reason(service: BrainService, params: P.ReasonParams) -> R.ReasoningWire:
    result = service.reason(_developer_from_wire(params.context), task=params.task)
    return _wire_reasoning(result)


def _handle_preferences(service: BrainService, params: P.UserParams) -> R.PreferencesResult:
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
    service: BrainService, params: P.UserParams
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
    service: BrainService, params: P.UserParams
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


def _handle_learning_status(
    service: BrainService, params: P.UserParams
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
    service: BrainService, params: P.FeedbackHistoryParams
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
    service: BrainService, params: P.UserParams
) -> R.AssistanceProfileResult:
    return _wire_profile(service.personalization_profile(params.user_id))


# -- registry (method -> (params model, result model, handler)) ------------------

_SPECS: dict[
    ApiMethod, tuple[type[BaseModel], type[BaseModel], Callable[[BrainService, BaseModel], BaseModel]]
] = {
    ApiMethod.PING: (P.PingParams, R.PingResult, _handle_ping),
    ApiMethod.DESCRIBE: (P.DescribeParams, R.DescribeResult, _handle_describe),
    ApiMethod.INGEST: (P.IngestParams, R.IngestionResultWire, _handle_ingest),
    ApiMethod.RECORD_FEEDBACK: (
        P.RecordFeedbackParams,
        R.FeedbackResultWire,
        _handle_record_feedback,
    ),
    ApiMethod.RECORD_PREFERENCE: (
        P.RecordPreferenceParams,
        R.PreferenceWire,
        _handle_record_preference,
    ),
    ApiMethod.UNDERSTAND: (
        P.UnderstandParams,
        R.UnderstandResultWire,
        _handle_understand,
    ),
    ApiMethod.BUILD_CONTEXT: (
        P.BuildContextParams,
        R.ContextResultWire,
        _handle_build_context,
    ),
    ApiMethod.ANALYZE_DEVELOPER: (
        P.AnalyzeDeveloperParams,
        R.AnalyzeDeveloperResult,
        _handle_analyze_developer,
    ),
    ApiMethod.REASON: (P.ReasonParams, R.ReasoningWire, _handle_reason),
    ApiMethod.PREFERENCES: (
        P.UserParams,
        R.PreferencesResult,
        _handle_preferences,
    ),
    ApiMethod.DEVELOPER_PREFERENCES: (
        P.UserParams,
        R.DeveloperPreferencesResult,
        _handle_developer_preferences,
    ),
    ApiMethod.PEOPLE_SUMMARY: (
        P.UserParams,
        R.PeopleSummaryResult,
        _handle_people_summary,
    ),
    ApiMethod.LEARNING_STATUS: (
        P.UserParams,
        R.LearningStatusResult,
        _handle_learning_status,
    ),
    ApiMethod.FEEDBACK_HISTORY: (
        P.FeedbackHistoryParams,
        R.FeedbackHistoryResult,
        _handle_feedback_history,
    ),
    ApiMethod.PERSONALIZATION_PROFILE: (
        P.UserParams,
        R.AssistanceProfileResult,
        _handle_personalization_profile,
    ),
}

_METHOD_VALUES = frozenset(method.value for method in ApiMethod)


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
        return [method.value for method in _SPECS]

    def describe(self) -> R.DescribeResult:
        return _handle_describe(self._service, P.DescribeParams())

    def handle(self, message: Mapping[str, Any]) -> ApiResponse[Any]:
        """Single entry point for any transport: mapping -> validated response."""
        raw_method = message.get("method")
        raw_version = message.get("version", _SUPPORTED_VERSION)
        request_id = str(message.get("id") or "").strip()

        if not isinstance(raw_method, str) or raw_method not in _METHOD_VALUES:
            return error_response(
                request_id,
                None,
                ApiError(
                    code=ApiErrorCode.UNKNOWN_METHOD,
                    message=f"unknown method: {raw_method!r}",
                    source="BrainApi",
                ),
            )
        method = ApiMethod(raw_method)
        if raw_version != _SUPPORTED_VERSION:
            return error_response(
                request_id,
                method,
                ApiError(
                    code=ApiErrorCode.VERSION_UNSUPPORTED,
                    message=f"unsupported contract version: {raw_version!r}",
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
        spec = _SPECS.get(request.method)
        if spec is None:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.UNKNOWN_METHOD,
                    message=f"method not implemented: {request.method.value}",
                    source="BrainApi",
                ),
            )
        params_cls, _, handler = spec
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
            result = handler(self._service, params)
        except ApiRequestValidationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.VALIDATION_ERROR,
                    message=str(exc),
                    source="BrainApi",
                ),
            )
        except BrainServiceValidationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.VALIDATION_ERROR,
                    message=str(exc),
                    source="BrainService",
                ),
            )
        except BrainServiceConfigurationError as exc:
            return error_response(
                request.id,
                request.method,
                ApiError(
                    code=ApiErrorCode.NOT_CONFIGURED,
                    message=str(exc),
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