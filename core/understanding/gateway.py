"""LLMGateway — provider-independent LLM access for Core Brain.

    LLMGateway
    ├── understand(...)             text/code -> validated UnderstandingResult
    ├── analyze(...)                DeveloperContext -> validated DeveloperAnalysis
    └── generate_structured(...)    arbitrary pydantic schema -> validated instance

Design rules (Phase 3 spec):

* Provider = text-completion port (see ``providers.py``). All structuring and
  validation happens HERE — raw/unvalidated LLM output can never flow further.
* Configurable selection via ``GatewayConfig`` + ``build_gateway``.
* ``understand``/``analyze`` fall back to a deterministic provider on timeout,
  provider failure or malformed output. ``generate_structured`` never silently
  falls back (no fabricated certainty) — it raises.
* ``analyze`` stamps user_id/repository/file stats from the TRUSTED
  DeveloperContext; values in LLM output never override them (isolation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from .developer import DeveloperAnalysis, DeveloperContext, context_corpus, summarize_context
from .exceptions import (
    InvalidLLMOutputError,
    LLMGatewayError,
    LLMProviderError,
    LLMTimeoutError,
    UnderstandingError,
)
from .models import UnderstandingResult
from .providers import LLMProvider, LLMRequest, create_provider
from .validation import parse_structured, parse_understanding

T = TypeVar("T", bound=BaseModel)
_SYSTEM_PROMPT = (
    "You are Core Brain, a deterministic analysis module. Return ONLY a JSON "
    "object matching the requested schema. No prose, no code fences required, "
    "no invented certainty. Confidence must reflect your actual certainty."
)


@dataclass(frozen=True)
class GatewayConfig:
    """Provider selection for :func:`build_gateway`."""

    provider: str = "heuristic"
    fallback_provider: str | None = "heuristic"
    timeout_seconds: float = 30.0


def build_gateway(config: GatewayConfig | None = None) -> "LLMGateway":
    """Instantiate a gateway from a config (provider selection is configurable)."""
    config = config or GatewayConfig()
    primary = create_provider(config.provider)
    fallback = (
        create_provider(config.fallback_provider)
        if config.fallback_provider
        else None
    )
    return LLMGateway(primary, fallback=fallback, timeout_seconds=config.timeout_seconds)


class LLMGateway:
    """Validates and interprets provider output for Core Brain."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        fallback: LLMProvider | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not isinstance(provider, LLMProvider):
            raise TypeError("provider must implement LLMProvider")
        self._primary = provider
        self._fallback = fallback
        self._timeout = timeout_seconds

    @property
    def provider(self) -> LLMProvider:
        return self._primary

    @property
    def fallback(self) -> LLMProvider | None:
        return self._fallback

    # -- public operations -------------------------------------------------
    def understand(
        self,
        corpus: str,
        *,
        user_id: str | None = None,
        corpus_id: str | None = None,
    ) -> UnderstandingResult:
        """Interpret unstructured text/code into a validated UnderstandingResult."""
        text = (corpus or "").strip()
        if not text:
            raise UnderstandingError("cannot understand an empty corpus")
        request = LLMRequest(
            operation="understand",
            system=_SYSTEM_PROMPT,
            user=_understand_prompt(text),
            params={"corpus": text},
            timeout_seconds=self._timeout,
        )
        return self._run(
            request,
            lambda raw, provider, fallback: parse_understanding(
                raw,
                provider=provider,
                fallback_used=fallback,
                user_id=user_id,
                corpus_id=corpus_id,
            ),
        )

    def analyze(self, context: DeveloperContext) -> DeveloperAnalysis:
        """Understand a DeveloperContext and wrap it with trusted stats."""
        corpus = context_corpus(context)
        understanding = self.understand(
            corpus,
            user_id=context.user_id,
            corpus_id=f"{context.repository}:{context.current_file or '<repo>'}",
        )
        stats = summarize_context(context)
        return DeveloperAnalysis(
            user_id=context.user_id,
            repository=context.repository,
            provider=understanding.provider,
            fallback_used=understanding.fallback_used,
            understanding=understanding,
            files_analyzed=stats["files_analyzed"],
            total_lines=stats["total_lines"],
            languages=stats["languages"],
            focus_file=stats["focus_file"],
            focus_line=stats["focus_line"],
            confidence=understanding.confidence,
        )

    def generate_structured(
        self,
        schema: type[T],
        *,
        system: str,
        user: str,
        **params: Any,
    ) -> T:
        """Generate+validate an arbitrary structured result (no silent fallback)."""
        request = LLMRequest(
            operation="generate_structured",
            system=system,
            user=user,
            params={"schema": schema.model_json_schema(), **params},
            timeout_seconds=self._timeout,
        )
        return self._run(
            request,
            lambda raw, _provider, _fallback: parse_structured(raw, schema),
            allow_fallback=False,
        )

    # -- primary -> fallback execution --------------------------------------
    def _run(
        self,
        request: LLMRequest,
        parse: Callable[[str, str, bool], T],
        *,
        allow_fallback: bool = True,
    ) -> T:
        primary_error: LLMGatewayError | None = None
        try:
            raw = self._primary.complete(request)
            return parse(raw, self._primary.name, False)
        except (LLMTimeoutError, LLMProviderError, InvalidLLMOutputError) as exc:
            primary_error = exc

        if not allow_fallback or self._fallback is None or self._fallback is self._primary:
            assert primary_error is not None
            raise primary_error

        try:
            raw = self._fallback.complete(request)
            return parse(raw, self._fallback.name, True)
        except (LLMTimeoutError, LLMProviderError, InvalidLLMOutputError) as exc:
            raise LLMGatewayError(
                f"primary provider failed: {primary_error}; "
                f"fallback provider failed: {exc}"
            ) from primary_error


def _understand_prompt(text: str) -> str:
    return (
        "Interpret the following corpus. Respond with strict JSON: "
        '{"intent": "<understand|explain|debug|implement|review|deploy|other>", '
        '"entities": ["..."], "topics": ["..."], '
        '"salience": <0..1>, "confidence": <0..1>, '
        '"summary": "<one clear sentence>", '
        '"relevant_code_concepts": ["..."]}. '
        "Lower confidence when you are guessing.\n\nCORPUS:\n"
        f"{text[:4000]}"
    )