"""Shared fixtures for understanding tests (stub LLM providers)."""

from __future__ import annotations

import json
from typing import Any

from core.understanding.exceptions import LLMProviderError, LLMTimeoutError
from core.understanding.providers import LLMRequest


def valid_understanding(**overrides: Any) -> str:
    body = {
        "intent": "debug",
        "entities": ["user", "email"],
        "topics": ["bug", "auth"],
        "salience": 0.8,
        "confidence": 0.7,
        "summary": "Possible null reference on user.email.",
        "relevant_code_concepts": ["getUser", "email"],
    }
    body.update(overrides)
    return json.dumps(body)


class ReturningProvider:
    """Fake provider that returns a fixed (or request-aware) response."""

    name = "stub-return"

    def __init__(self, response: str, *, name: str = "stub-return") -> None:
        self._response = response
        self.name = name
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> str:
        self.requests.append(request)
        return self._response


class TimeoutProvider:
    name = "stub-timeout"

    def complete(self, request: LLMRequest) -> str:
        raise LLMTimeoutError("simulated provider timeout")


class ProviderFailureProvider:
    name = "stub-failure"

    def complete(self, request: LLMRequest) -> str:
        raise LLMProviderError("simulated provider outage")


class RecordingProvider:
    """Fake provider that records requests and returns a fixed response."""

    name = "stub-record"

    def __init__(self, response: str, *, name: str = "stub-record") -> None:
        self._response = response
        self.name = name
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> str:
        self.requests.append(request)
        return self._response