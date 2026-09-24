"""Understanding / LLM-gateway exception hierarchy.

Structured errors, no silent success: every failure path is explicit so the
Caller (Reasoning, later phases) can decide whether the heuristic fallback is
acceptable.
"""


class UnderstandingError(Exception):
    """Base error for the Understanding module."""


class LLMGatewayError(UnderstandingError):
    """Base error for the LLM gateway (timeout / provider / output problems)."""


class LLMTimeoutError(LLMGatewayError):
    """The provider did not answer within the configured timeout."""


class LLMProviderError(LLMGatewayError):
    """The provider failed (network, auth, unsupported operation, etc.)."""


class InvalidLLMOutputError(LLMGatewayError, ValueError):
    """The provider returned text that is not valid structured output."""