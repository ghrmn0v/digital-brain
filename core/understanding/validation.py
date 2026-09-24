"""Strict validation of provider output.

The gateway funnels every provider response through this module: JSON is
extracted and validated against the target pydantic schema. Anything that does
not conform raises :class:`InvalidLLMOutputError` — the gateway can then use
the deterministic fallback instead of propagating untrusted data.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .exceptions import InvalidLLMOutputError
from .models import UnderstandingResult

_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*(.*?)\s*```$", re.DOTALL)


def extract_json_object(raw: str) -> dict[str, Any]:
    """Extract a JSON object from provider text, allowing a code fence."""
    text = (raw or "").strip()
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidLLMOutputError(f"provider returned malformed JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InvalidLLMOutputError(
            f"expected a JSON object, got {type(value).__name__}"
        )
    return value


def parse_understanding(
    raw: str,
    *,
    provider: str,
    fallback_used: bool,
    user_id: str | None,
    corpus_id: str | None,
) -> UnderstandingResult:
    """Validate raw text into UnderstandingResult, stamping trusted fields."""
    try:
        data = extract_json_object(raw)
        return UnderstandingResult.model_validate(
            {
                **data,
                "provider": provider,
                "fallback_used": fallback_used,
                "user_id": user_id,
                "corpus_id": corpus_id,
            }
        )
    except InvalidLLMOutputError:
        raise
    except (ValidationError, ValueError, TypeError) as exc:
        raise InvalidLLMOutputError(
            f"structured output failed validation: {exc}"
        ) from exc


def parse_structured(raw: str, schema: type[Any]) -> Any:
    """Validate raw text against an arbitrary pydantic schema."""
    try:
        data = extract_json_object(raw)
        return schema.model_validate(data)
    except InvalidLLMOutputError:
        raise
    except (ValidationError, ValueError, TypeError) as exc:
        raise InvalidLLMOutputError(
            f"structured output for {getattr(schema, '__name__', 'schema')} "
            f"failed validation: {exc}"
        ) from exc