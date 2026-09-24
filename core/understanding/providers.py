"""Provider abstraction for the LLM gateway.

A provider is a pure TEXT completion port: it receives an :class:`LLMRequest`
and returns a string (for this MVP, JSON text). All structuring and validation
happens in the gateway — a provider can never inject unvalidated data upward.

:class:`HeuristicProvider` is a deterministic, offline implementation used as
the default provider AND as the fallback for ``understand``/``analyze``. It is
honest: low fixed confidence, keyword-based, no fabricated certainty.

Provider selection is configurable via ``register_provider`` /
``create_provider`` — any real provider (OpenAI, Anthropic, local model)
registers behind the same port without touching gateway logic.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

from .exceptions import LLMProviderError

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "you", "from", "has", "have",
    "are", "was", "were", "not", "but", "its", "into", "will", "should",
    "would", "about", "your", "code", "function", "returns",
}

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bug": ("bug", "defect", "crash", "broken"),
    "error": ("error", "exception", "throw", "undefined", "null", "panic"),
    "test": ("test", "testing", "coverage", "pytest", "jest", "assert"),
    "api": ("api", "endpoint", "request", "response", "http"),
    "auth": ("auth", "login", "session", "token", "password", "permission"),
    "database": ("database", "db", "sql", "query", "migration", "schema"),
    "performance": ("performance", "slow", "latency", "optimize", "cache"),
    "security": ("security", "injection", "sanitize", "csrf", "xss"),
    "deploy": ("deploy", "deployment", "release", "ci", "pipeline"),
    "refactor": ("refactor", "cleanup", "simplify", "duplicate", "legacy"),
}

_INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("debug", ("bug", "error", "exception", "undefined", "null", "panic",
               "traceback", "crash")),
    ("explain", ("explain", "why", "how", "summarize", "meaning")),
    ("review", ("review", "feedback", "pull request", "pr", "reviewing")),
    ("implement", ("implement", "add", "create", "write", "build", "refactor",
                   "feature")),
    ("deploy", ("deploy", "release", "publish", "rollout", "ship")),
)

_HEURISTIC_CONFIDENCE = 0.2  # deliberately low: keyword heuristics, not AI


@dataclass(frozen=True)
class LLMRequest:
    """A single completion request passed to a provider."""

    operation: str
    system: str
    user: str
    params: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 30.0


@runtime_checkable
class LLMProvider(Protocol):
    """Text-completion port. Raises LLMGatewayError subclasses on failure."""

    name: str

    def complete(self, request: LLMRequest) -> str: ...


class HeuristicProvider:
    """Deterministic offline provider (default + fallback for the MVP)."""

    name = "heuristic"

    def __init__(self, *, max_entities: int = 8, max_topics: int = 6) -> None:
        self._max_entities = max_entities
        self._max_topics = max_topics

    def complete(self, request: LLMRequest) -> str:
        if request.operation in ("understand", "analyze"):
            corpus = request.params.get("corpus", "") or ""
            return json.dumps(self._understand(corpus), ensure_ascii=False)
        raise LLMProviderError(
            f"heuristic provider does not support operation {request.operation!r}"
        )

    def _understand(self, corpus: str) -> dict[str, Any]:
        lowered = corpus.lower()
        topics = self._topics(lowered)
        intent = self._intent(lowered)
        identifiers = self._identifiers(corpus)
        keywords_hit = len(topics) + (1 if intent != "understand" else 0)
        salience = round(min(0.9, 0.3 + 0.08 * keywords_hit), 2)
        return {
            "intent": intent,
            "entities": identifiers[: self._max_entities],
            "topics": topics,
            "salience": salience,
            "confidence": _HEURISTIC_CONFIDENCE,
            "summary": _collapse(corpus, limit=200),
            "relevant_code_concepts": identifiers[: self._max_entities],
        }

    def _topics(self, lowered: str) -> list[str]:
        found: list[str] = []
        for topic, keywords in _TOPIC_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                found.append(topic)
            if len(found) >= self._max_topics:
                break
        return found

    def _intent(self, lowered: str) -> str:
        for intent, keywords in _INTENT_KEYWORDS:
            if any(keyword in lowered for keyword in keywords):
                return intent
        return "understand"

    def _identifiers(self, corpus: str) -> list[str]:
        counts: Counter[str] = Counter()
        for match in _IDENT_RE.finditer(corpus):
            token = match.group(0)
            if token.lower() in _STOPWORDS:
                continue
            counts[token] += 1
        return [token for token, _ in counts.most_common(self._max_entities)]


def _collapse(corpus: str, *, limit: int) -> str:
    single = " ".join(corpus.split())
    return single[:limit] or "Empty input."


# -- provider registry (configurable selection) ----------------------------
_PROVIDER_FACTORIES: dict[str, Callable[[], LLMProvider]] = {}


def register_provider(name: str, factory: Callable[[], LLMProvider]) -> None:
    """Register a provider factory under a selectable name."""
    _PROVIDER_FACTORIES[name] = factory


def create_provider(name: str) -> LLMProvider:
    """Instantiate a registered provider by name."""
    factory = _PROVIDER_FACTORIES.get(name)
    if factory is None:
        raise LLMProviderError(f"unknown LLM provider {name!r}")
    return factory()


register_provider("heuristic", lambda: HeuristicProvider())