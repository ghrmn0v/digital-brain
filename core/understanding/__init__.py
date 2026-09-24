"""Core Brain Understanding module (Phase 3).

Provider-independent LLM access plus validated structured interpretation for
Core Brain. Nothing here executes external actions; results are plain data for
Reasoning/later phases.

See ``docs/understanding.md`` and ``docs/developer-mode/SPEC.md``.
"""

from .developer import (
    DeveloperAnalysis,
    DeveloperContext,
    DeveloperFile,
    GitContext,
    TestResultSnapshot,
    context_corpus,
    summarize_context,
)
from .exceptions import (
    InvalidLLMOutputError,
    LLMGatewayError,
    LLMProviderError,
    LLMTimeoutError,
    UnderstandingError,
)
from .gateway import GatewayConfig, LLMGateway, build_gateway
from .models import UnderstandingIntent, UnderstandingResult
from .providers import (
    HeuristicProvider,
    LLMProvider,
    LLMRequest,
    create_provider,
    register_provider,
)
from .validation import extract_json_object, parse_structured, parse_understanding

__all__ = [
    "DeveloperAnalysis",
    "DeveloperContext",
    "DeveloperFile",
    "GatewayConfig",
    "GitContext",
    "HeuristicProvider",
    "InvalidLLMOutputError",
    "LLMGateway",
    "LLMGatewayError",
    "LLMProvider",
    "LLMProviderError",
    "LLMRequest",
    "LLMTimeoutError",
    "TestResultSnapshot",
    "UnderstandingError",
    "UnderstandingIntent",
    "UnderstandingResult",
    "build_gateway",
    "context_corpus",
    "create_provider",
    "extract_json_object",
    "parse_structured",
    "parse_understanding",
    "register_provider",
    "summarize_context",
]