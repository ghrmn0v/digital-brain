"""Canonical public registry for Digital Brain API v1 method contracts."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import BaseModel

from . import params, results
from .methods import ApiMethod

API_CONTRACT_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class ApiMethodSpec:
    """One stable method-to-model contract binding."""

    method: ApiMethod
    params_model: type[BaseModel]
    result_model: type[BaseModel]


API_METHOD_SPECS: tuple[ApiMethodSpec, ...] = (
    ApiMethodSpec(ApiMethod.PING, params.PingParams, results.PingResult),
    ApiMethodSpec(
        ApiMethod.DESCRIBE,
        params.DescribeParams,
        results.DescribeResult,
    ),
    ApiMethodSpec(
        ApiMethod.INGEST,
        params.IngestParams,
        results.IngestionResultWire,
    ),
    ApiMethodSpec(
        ApiMethod.RECORD_FEEDBACK,
        params.RecordFeedbackParams,
        results.FeedbackResultWire,
    ),
    ApiMethodSpec(
        ApiMethod.RECORD_PREFERENCE,
        params.RecordPreferenceParams,
        results.PreferenceWire,
    ),
    ApiMethodSpec(
        ApiMethod.UNDERSTAND,
        params.UnderstandParams,
        results.UnderstandResultWire,
    ),
    ApiMethodSpec(
        ApiMethod.BUILD_CONTEXT,
        params.BuildContextParams,
        results.ContextResultWire,
    ),
    ApiMethodSpec(
        ApiMethod.ANALYZE_DEVELOPER,
        params.AnalyzeDeveloperParams,
        results.AnalyzeDeveloperResult,
    ),
    ApiMethodSpec(ApiMethod.REASON, params.ReasonParams, results.ReasoningWire),
    ApiMethodSpec(
        ApiMethod.PREFERENCES,
        params.UserParams,
        results.PreferencesResult,
    ),
    ApiMethodSpec(
        ApiMethod.DEVELOPER_PREFERENCES,
        params.UserParams,
        results.DeveloperPreferencesResult,
    ),
    ApiMethodSpec(
        ApiMethod.PEOPLE_SUMMARY,
        params.UserParams,
        results.PeopleSummaryResult,
    ),
    ApiMethodSpec(
        ApiMethod.PEOPLE_TIMELINE,
        params.PeopleTimelineParams,
        results.PeopleTimelineResult,
    ),
    ApiMethodSpec(
        ApiMethod.LEARNING_STATUS,
        params.UserParams,
        results.LearningStatusResult,
    ),
    ApiMethodSpec(
        ApiMethod.FEEDBACK_HISTORY,
        params.FeedbackHistoryParams,
        results.FeedbackHistoryResult,
    ),
    ApiMethodSpec(
        ApiMethod.PERSONALIZATION_PROFILE,
        params.UserParams,
        results.AssistanceProfileResult,
    ),
    ApiMethodSpec(
        ApiMethod.RESOLVE_PERSON,
        params.ResolvePersonParams,
        results.PersonResolutionWire,
    ),
    # Appended, not inserted: a client that learned an earlier method index
    # keeps it. Both are additive reads/derived answers over data the Brain
    # already owned, exposed so the Brain can be used without a UI.
    ApiMethodSpec(ApiMethod.SEARCH, params.SearchParams, results.SearchResultWire),
    ApiMethodSpec(ApiMethod.CHAT, params.ChatParams, results.ChatResultWire),
)

API_METHOD_REGISTRY: Mapping[ApiMethod, ApiMethodSpec] = MappingProxyType(
    {spec.method: spec for spec in API_METHOD_SPECS}
)


def api_method_names() -> list[str]:
    """Return method names in stable contract order."""
    return [spec.method.value for spec in API_METHOD_SPECS]


def get_api_method_spec(method: ApiMethod | str) -> ApiMethodSpec:
    """Return the public contract spec for one enum member or method name."""
    resolved = method if isinstance(method, ApiMethod) else ApiMethod(method)
    return API_METHOD_REGISTRY[resolved]


def describe_api_methods() -> dict[str, dict[str, dict[str, Any]]]:
    """Build the same per-method JSON Schemas exposed by ``BrainApi.describe``."""
    return {
        spec.method.value: {
            "params": spec.params_model.model_json_schema(),
            "result": spec.result_model.model_json_schema(),
        }
        for spec in API_METHOD_SPECS
    }


__all__ = [
    "API_CONTRACT_VERSION",
    "API_METHOD_REGISTRY",
    "API_METHOD_SPECS",
    "ApiMethodSpec",
    "api_method_names",
    "describe_api_methods",
    "get_api_method_spec",
]
