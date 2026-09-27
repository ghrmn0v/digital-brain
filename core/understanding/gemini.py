"""Gemini provider for the existing LLM gateway (additive, provider-port only).

This module adds ONE implementation of the existing
:class:`core.understanding.providers.LLMProvider` port. It does not introduce a
new architecture, a new gateway, a new registry or a parallel memory: the
gateway keeps owning selection, validation and fallback, and this file only
speaks the Gemini wire format.

Boundaries kept on purpose:

* Gemini is a *reasoning* component only. It never writes memory: the provider
  returns text, and the gateway validates it into a Brain model.
* Provider-specific shapes (REST paths, headers, response envelope) stay here.
  Nothing Gemini-shaped leaks into Core APIs, events or errors.
* Credentials come from configuration, never from a literal, and are never
  logged, returned, echoed in an error, or attached to an event.
* Only the standard library is used (``urllib``) — no new dependency.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping

from core.config import (
    ENV_GEMINI_API_KEY,
    ENV_GEMINI_API_BASE,
    ENV_GEMINI_ENABLED,
    ENV_GEMINI_MAX_OUTPUT_TOKENS,
    ENV_GEMINI_MODEL,
    ENV_GEMINI_TEMPERATURE,
    ENV_GEMINI_TIMEOUT,
)
from core.observability import register_secret

from .exceptions import (
    InvalidLLMOutputError,
    LLMProviderError,
    LLMTimeoutError,
)
from .providers import LLMProvider, LLMRequest, register_provider

_DEFAULT_API_BASE = "https://generativelanguage.googleapis.com"
_DEFAULT_MODEL = "gemini-3.8-flash"
#: Statuses that mean "not now", as opposed to "not ever". A 503 or 429 is
#: capacity or a burst limit, and one more attempt after a short pause usually
#: succeeds; a 400, 403 or 404 is the request itself and retrying is pointless.
_RETRYABLE_STATUSES = frozenset({429, 503})
_RETRY_BACKOFF_SECONDS = 1.5


class _TransientStatus(Exception):
    """Internal marker: a status worth one more attempt.

    It never leaves this module. :meth:`GeminiProvider._post` unwraps it so that
    callers only ever see the typed ``LLMGatewayError`` they already handle.
    """
# Re-exported from core.config so both modules agree on one definition.
ENV_API_KEY = ENV_GEMINI_API_KEY
ENV_MODEL = ENV_GEMINI_MODEL
ENV_ENABLED = ENV_GEMINI_ENABLED
ENV_API_BASE = ENV_GEMINI_API_BASE
ENV_TIMEOUT = ENV_GEMINI_TIMEOUT
ENV_TEMPERATURE = ENV_GEMINI_TEMPERATURE
ENV_MAX_OUTPUT_TOKENS = ENV_GEMINI_MAX_OUTPUT_TOKENS

_REDACTED = "***"


def _truthy(value: str | None, *, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _number(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class GeminiConfig:
    """Provider configuration.

    ``api_key`` is the only secret. It is held here and never copied into a
    prompt, a result, an event or an error message.
    """

    api_key: str = ""
    #: Only a default. Production sets GEMINI_MODEL so the model can change
    #: without touching Brain logic.
    model: str = _DEFAULT_MODEL
    enabled: bool = False
    api_base: str = _DEFAULT_API_BASE
    timeout_seconds: float = 30.0
    temperature: float = 0.2
    max_output_tokens: int = 2048
    max_user_chars: int = 32_000

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.api_key.strip() and self.model.strip())

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GeminiConfig":
        """Read configuration from the environment.

        The Brain has no other configuration source, so this is the single
        place Gemini settings enter the process. Reading is explicit and
        lazy: nothing is read at import time.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        api_key = (source.get(ENV_API_KEY) or "").strip()
        # Register the credential as non-emittable the moment it is read, so a
        # provider error or any future log statement cannot echo it.
        register_secret(api_key)
        return cls(
            api_key=api_key,
            model=(source.get(ENV_MODEL) or _DEFAULT_MODEL).strip() or _DEFAULT_MODEL,
            enabled=_truthy(source.get(ENV_ENABLED), default=False),
            api_base=(
                (source.get(ENV_API_BASE) or _DEFAULT_API_BASE).strip().rstrip("/")
                or _DEFAULT_API_BASE
            ),
            timeout_seconds=_number(source.get(ENV_TIMEOUT), 30.0),
            temperature=_number(source.get(ENV_TEMPERATURE), 0.2),
            max_output_tokens=int(
                _number(source.get(ENV_MAX_OUTPUT_TOKENS), 2048)
            ),
        )

    def redacted(self) -> "GeminiConfig":
        """A copy safe to log or attach to diagnostics."""
        return replace_config(self, api_key=_REDACTED if self.api_key else "")


def replace_config(config: GeminiConfig, **changes: Any) -> GeminiConfig:
    values = {
        "api_key": config.api_key,
        "model": config.model,
        "enabled": config.enabled,
        "api_base": config.api_base,
        "timeout_seconds": config.timeout_seconds,
        "temperature": config.temperature,
        "max_output_tokens": config.max_output_tokens,
        "max_user_chars": config.max_user_chars,
    }
    values.update(changes)
    return GeminiConfig(**values)


@dataclass
class GeminiUsage:
    """Provider-reported counters, exposed for observability only."""

    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    fallback_triggered_count: int = 0
    last_model: str = ""
    last_error: str = ""


class GeminiProvider:
    """Gemini as a text-completion port.

    Implements the existing :class:`LLMProvider` interface: a request in, text
    out. All structuring and validation stays in the gateway.
    """

    name = "gemini"

    def __init__(
        self,
        config: GeminiConfig | None = None,
        *,
        opener: Any | None = None,
    ) -> None:
        self._config = config or GeminiConfig()
        # Injectable transport seam so tests never touch the network.
        self._opener = opener if opener is not None else urllib.request.urlopen
        self._usage = GeminiUsage()

    @property
    def config(self) -> GeminiConfig:
        return self._config

    @property
    def is_configured(self) -> bool:
        return self._config.is_configured

    @property
    def usage(self) -> GeminiUsage:
        return self._usage

    # -- LLMProvider port ---------------------------------------------------
    def complete(self, request: LLMRequest) -> str:
        """Return the model's text for one request, or raise a typed error."""
        if not self._config.enabled:
            self._count_failure("provider disabled")
            raise LLMProviderError("gemini provider is disabled")
        if not self._config.api_key.strip():
            self._count_failure("missing api key")
            raise LLMProviderError("gemini provider has no API key configured")
        if not self._config.model.strip():
            self._count_failure("missing model")
            raise LLMProviderError("gemini provider has no model configured")

        self._usage.request_count += 1
        self._usage.last_model = self._config.model
        payload = self._build_payload(request)
        raw = self._post(payload, timeout=self._timeout_for(request))
        return self._text_of(raw)

    # -- request / response translation ------------------------------------
    def _build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Brain request -> Gemini ``generateContent`` body.

        The user text is bounded here as well as in the gateway: a prompt
        limit is a privacy limit, and only necessary content should leave the
        process.
        """
        system = _with_schema(request.system, request.params.get("schema"))
        user_text = (request.user or "")[: self._config.max_user_chars]
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "temperature": self._config.temperature,
                "maxOutputTokens": self._config.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    def _endpoint(self) -> str:
        return f"{self._config.api_base}/v1beta/models/{self._config.model}:generateContent"

    def _headers(self) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "x-goog-api-key": self._config.api_key,
        }

    def _timeout_for(self, request: LLMRequest) -> float:
        timeout = request.timeout_seconds or self._config.timeout_seconds
        return float(timeout) if timeout and timeout > 0 else self._config.timeout_seconds

    def _post(self, payload: dict[str, Any], *, timeout: float) -> str:
        # A hosted model answers 503 and 429 for reasons that have nothing to do
        # with the request: no capacity behind the endpoint, or a burst limit.
        # Retrying once after a short pause turns most of those into a normal
        # answer. It is deliberately one retry and only for those two statuses:
        # a bad request, a refused request or a missing key must fail at once,
        # and a retry storm would just turn an outage into a bill.
        last: Exception | None = None
        for attempt in range(2):
            try:
                return self._post_once(payload, timeout=timeout)
            except _TransientStatus as transient:
                last = transient.__cause__ or transient
                if attempt == 0:
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                    continue
                raise last from None
        raise last if last else LLMProviderError("gemini request failed")  # pragma: no cover

    def _post_once(self, payload: dict[str, Any], *, timeout: float) -> str:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(
            self._endpoint(),
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with self._opener(http_request, timeout=timeout) as response:
                status = getattr(response, "status", 200) or 200
                raw = response.read()
        except urllib.error.HTTPError as exc:
            error = self._http_error(exc)
            if exc.code in _RETRYABLE_STATUSES:
                raise _TransientStatus(str(exc.code)) from error
            raise error from exc
        except socket.timeout as exc:
            self._count_failure("timeout")
            raise LLMTimeoutError("gemini request timed out") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, socket.timeout):
                self._count_failure("timeout")
                raise LLMTimeoutError("gemini request timed out") from exc
            self._count_failure("network error")
            raise LLMProviderError(
                f"gemini request failed: {_redact(str(reason), self._config.api_key)}"
            ) from exc
        except TimeoutError as exc:  # pragma: no cover - alias path
            self._count_failure("timeout")
            raise LLMTimeoutError("gemini request timed out") from exc
        except OSError as exc:  # pragma: no cover - defensive
            self._count_failure("network error")
            raise LLMProviderError(
                f"gemini request failed: {_redact(str(exc), self._config.api_key)}"
            ) from exc
        if int(status) >= 400:
            error = self._status_error(int(status))
            if int(status) in _RETRYABLE_STATUSES:
                raise _TransientStatus(str(status)) from error
            raise error
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    def _text_of(self, raw: str) -> str:
        """Gemini envelope -> text. Anything unusable is a typed failure."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            self._count_failure("malformed response")
            raise LLMProviderError("gemini returned a non-JSON response") from exc
        if not isinstance(data, dict):
            self._count_failure("malformed response")
            raise LLMProviderError("gemini returned a non-object response")
        blocked = _blocked_reason(data)
        if blocked is not None:
            self._count_failure(blocked)
            raise LLMProviderError(f"gemini refused the request: {blocked}")
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            self._count_failure("empty response")
            raise InvalidLLMOutputError("gemini returned no candidates")
        parts = ((candidates[0] or {}).get("content") or {}).get("parts")
        if not isinstance(parts, list) or not parts:
            self._count_failure("empty response")
            raise InvalidLLMOutputError("gemini returned no text parts")
        text = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
        if not text.strip():
            self._count_failure("empty response")
            raise InvalidLLMOutputError("gemini returned an empty completion")
        self._usage.success_count += 1
        return text

    # -- errors -------------------------------------------------------------
    def _http_error(self, exc: urllib.error.HTTPError) -> LLMProviderError:
        status = int(getattr(exc, "code", 0) or 0)
        if status == 429:
            # A 429 is two different problems wearing the same status code.
            # Google's own body separates them: a spent quota is
            # ``RESOURCE_EXHAUSTED`` with a ``quotaId`` naming the window, while
            # a burst limit is a plain rejection that clears in seconds. Both
            # mean "not now", but only one of them clears on its own, and an
            # operator told "rate limit reached" will wait a moment and then
            # conclude the provider is broken when the real answer is that the
            # free tier is capped. Only the window name is lifted out of the
            # body — never the body text, which can echo the request.
            window = _quota_window(exc)
            if window is not None:
                return self._fail(f"gemini quota exhausted ({window})")
            return self._fail("gemini rate limit reached")
        if status in (401, 403):
            # Never surface provider auth payloads: they can echo credentials.
            return self._fail("gemini authentication failed")
        return self._status_error(status)

    def _status_error(self, status: int) -> LLMProviderError:
        if 500 <= status < 600:
            return self._fail(f"gemini server error (HTTP {status})")
        return self._fail(f"gemini request rejected (HTTP {status})")

    def _fail(self, message: str) -> LLMProviderError:
        self._count_failure(message)
        return LLMProviderError(_redact(message, self._config.api_key))

    def _count_failure(self, reason: str) -> None:
        self._usage.failure_count += 1
        self._usage.last_error = _redact(reason, self._config.api_key)


def _with_schema(system: str, schema: Any) -> str:
    """Ask for JSON matching the requested schema.

    The schema travels as instruction text rather than as Gemini's
    ``responseJsonSchema``: that field accepts only a subset of JSON Schema, and
    sending an unsupported construct turns into a hard 400 instead of a softer
    formatting slip. The gateway validates the result either way, so the
    instruction form degrades safely.
    """
    if not isinstance(schema, dict) or not schema:
        return system
    try:
        rendered = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return system
    return (
        f"{system}\n\nThe response must validate against this JSON schema:\n"
        f"{rendered[:6000]}"
    )


def _blocked_reason(data: Mapping[str, Any]) -> str | None:
    feedback = data.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        return f"blockReason={feedback['blockReason']}"
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        reason = (candidates[0] or {}).get("finishReason")
        if isinstance(reason, str) and reason.upper() in {"SAFETY", "RECITATION", "BLOCKLIST"}:
            return f"finishReason={reason}"
    return None


def _redact(message: str, api_key: str) -> str:
    """Defensive: never let a credential reach a log or an error payload."""
    if api_key and api_key in message:
        return message.replace(api_key, _REDACTED)
    return message


#: Maps the ``quotaId`` Google reports onto the window a human would name. A
#: value that is not in here is deliberately not guessed at: an unrecognised
#: quota is treated as a transient limit rather than described wrongly.
_QUOTA_WINDOWS = (
    ("perminute", "per-minute limit"),
    ("perday", "daily limit"),
    ("perhour", "hourly limit"),
)


#: Distinguishes "computed and there is no quota" from "not computed yet", since
#: ``None`` is a real answer here.
_QUOTA_WINDOW_UNSET = object()


def _quota_window(exc: urllib.error.HTTPError) -> str | None:
    """Name the quota window from a 429 body, or ``None`` if it is not a quota.

    The answer is memoised on the exception, and that is not an optimisation. A
    429 is retryable, so ``_post`` raises the *same* ``HTTPError`` object twice —
    and an ``HTTPError`` is a one-shot stream. Reading it on the first attempt
    leaves the second attempt with an empty body, which reads as "no quota here"
    and silently downgrades a precise diagnosis to "rate limit reached". Since
    every 429 is retried, without this the specific message would never survive
    to the caller.

    The body is read once and only a window name looked up in a fixed table is
    returned; nothing from the payload becomes part of a message, because that
    payload can echo the request. Any failure to read or parse it is treated as
    "not a quota", which loses one word of detail rather than failing a request.
    """
    cached = getattr(exc, "_cerbro_quota_window", _QUOTA_WINDOW_UNSET)
    if cached is not _QUOTA_WINDOW_UNSET:
        return cached  # type: ignore[return-value]

    window = _read_quota_window(exc)
    try:
        setattr(exc, "_cerbro_quota_window", window)
    except Exception:  # pragma: no cover - defensive
        pass
    return window


def _read_quota_window(exc: urllib.error.HTTPError) -> str | None:
    try:
        raw = exc.read()
    except Exception:  # pragma: no cover - defensive
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None

    error = data.get("error")
    if not isinstance(error, dict) or error.get("status") != "RESOURCE_EXHAUSTED":
        return None

    quota_ids: list[str] = []
    for detail in error.get("details") or []:
        if not isinstance(detail, dict):
            continue
        quota_id = detail.get("quotaId")
        if isinstance(quota_id, str):
            quota_ids.append(quota_id)
        for violation in detail.get("violations") or []:
            if isinstance(violation, dict) and isinstance(
                violation.get("quotaId"), str
            ):
                quota_ids.append(violation["quotaId"])

    lowered = " ".join(quota_ids).lower()
    for needle, window in _QUOTA_WINDOWS:
        if needle in lowered:
            return window
    # Exhausted, but the window is one this build does not name. Saying so is
    # still more useful than calling it a rate limit.
    return "quota exhausted" if quota_ids else None


def _gemini_factory() -> LLMProvider:
    """Registry factory: configuration is read lazily, per instantiation."""
    return GeminiProvider(GeminiConfig.from_env())


def register_gemini_provider() -> None:
    """Register ``gemini`` with the existing provider registry (idempotent)."""
    register_provider("gemini", _gemini_factory)


register_gemini_provider()
