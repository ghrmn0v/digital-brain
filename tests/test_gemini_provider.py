"""Gemini provider against the existing LLMProvider port (additive slice).

No network: the provider takes an injectable ``opener`` transport seam, so
every test exercises the real request/response translation with a fake HTTP
layer. The gateway's selection/validation/fallback behaviour is tested as-is,
because that is the behaviour a real provider plugs into.
"""

from __future__ import annotations

import io
import json
import unittest
import urllib.error

from core.understanding import (
    GatewayConfig,
    GeminiConfig,
    GeminiProvider,
    HeuristicProvider,
    LLMGateway,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMTimeoutError,
    UnderstandingResult,
    build_gateway,
    create_provider,
    register_gemini_provider,
)
from core.understanding.exceptions import InvalidLLMOutputError

REQUEST = LLMRequest(
    operation="understand",
    system="Return JSON.",
    user="Interpret: the parser crashes on empty input",
    params={"corpus": "the parser crashes on empty input"},
    timeout_seconds=5.0,
)


def gemini_text(text: str) -> dict:
    """A well-formed Gemini generateContent response."""
    return {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 30},
    }


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def provider_with(payload: dict, *, status: int = 200, error: Exception | None = None,
                  config: GeminiConfig | None = None) -> tuple[GeminiProvider, dict]:
    built: dict[str, object] = {}

    def opener(request, timeout=None):  # type: ignore[no-untyped-def]
        built["url"] = request.full_url
        built["headers"] = dict(request.header_items())
        built["body"] = json.loads(request.data.decode("utf-8"))
        built["method"] = request.get_method()
        built["timeout"] = timeout
        if error is not None:
            raise error
        return FakeResponse(payload, status)

    cfg = config or GeminiConfig(
        api_key="test-key-not-real", model="gemini-2.0-flash", enabled=True
    )
    return GeminiProvider(cfg, opener=opener), built


class GeminiProviderPortTests(unittest.TestCase):
    def test_provider_implements_the_existing_port(self) -> None:
        provider, _ = provider_with(gemini_text("{}"))
        self.assertIsInstance(provider, LLMProvider)
        self.assertEqual(provider.name, "gemini")

    def test_provider_is_registered_in_the_existing_registry(self) -> None:
        register_gemini_provider()
        provider = create_provider("gemini")
        self.assertEqual(provider.name, "gemini")
        # The default provider is untouched.
        self.assertEqual(create_provider("heuristic").name, "heuristic")

    def test_gateway_can_select_gemini_by_name(self) -> None:
        gateway = build_gateway(
            GatewayConfig(provider="gemini", fallback_provider="heuristic")
        )
        self.assertEqual(gateway.provider.name, "gemini")
        self.assertEqual(gateway.fallback.name, "heuristic")


class GeminiConfigurationTests(unittest.TestCase):
    def test_missing_key_is_not_configured(self) -> None:
        config = GeminiConfig.from_env({"GEMINI_ENABLED": "true"})
        self.assertFalse(config.is_configured)
        provider = GeminiProvider(config, opener=lambda *a, **k: None)
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("no API key", str(caught.exception))

    def test_disabled_provider_is_not_configured(self) -> None:
        config = GeminiConfig.from_env(
            {"GEMINI_API_KEY": "k", "GEMINI_ENABLED": "false"}
        )
        self.assertFalse(config.is_configured)
        provider = GeminiProvider(config, opener=lambda *a, **k: None)
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("disabled", str(caught.exception))

    def test_enabled_with_key_is_configured(self) -> None:
        config = GeminiConfig.from_env(
            {"GEMINI_API_KEY": "k", "GEMINI_ENABLED": "true"}
        )
        self.assertTrue(config.is_configured)

    def test_model_is_configurable_not_hardcoded_in_logic(self) -> None:
        first = GeminiConfig.from_env({"GEMINI_API_KEY": "k", "GEMINI_ENABLED": "1",
                                       "GEMINI_MODEL": "gemini-a"})
        second = GeminiConfig.from_env({"GEMINI_API_KEY": "k", "GEMINI_ENABLED": "1",
                                        "GEMINI_MODEL": "gemini-b"})
        provider, seen = provider_with(
            gemini_text("{}"), config=first
        )
        provider.complete(REQUEST)
        self.assertIn("gemini-a", str(seen["url"]))
        self.assertNotIn("gemini-b", str(seen["url"]))
        provider2, seen2 = provider_with(
            gemini_text("{}"), config=second
        )
        provider2.complete(REQUEST)
        self.assertIn("gemini-b", str(seen2["url"]))

    def test_key_is_never_logged_or_returned(self) -> None:
        secret = "super-secret-key-value"
        config = GeminiConfig(api_key=secret, enabled=True)
        provider = GeminiProvider(config, opener=lambda *a, **k: None)
        self.assertEqual(provider.config.redacted().api_key, "***")
        self.assertNotEqual(provider.config.redacted().api_key, secret)
        self.assertEqual(provider.config.api_key, secret)
        # Even a real provider failure must not echo the key anywhere.
        error = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b""))
        failing, _ = provider_with({}, error=error, config=config)
        with self.assertRaises(LLMProviderError) as caught:
            failing.complete(REQUEST)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, failing.usage.last_error)
        self.assertNotIn(secret, str(failing.usage.last_error))


class GeminiRequestTranslationTests(unittest.TestCase):
    def test_request_maps_to_gemini_generate_content(self) -> None:
        provider, seen = provider_with(
            gemini_text(json.dumps({"intent": "debug", "entities": [], "topics": ["bug"],
                                    "salience": 0.5, "confidence": 0.4,
                                    "summary": "s", "relevant_code_concepts": []}))
        )
        provider.complete(REQUEST)
        self.assertEqual(seen["method"], "POST")
        self.assertIn(":generateContent", str(seen["url"]))
        self.assertIn("/v1beta/models/", str(seen["url"]))
        self.assertEqual(seen["headers"].get("X-goog-api-key"), "test-key-not-real")
        body = seen["body"]
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertIn("crashes on empty input", body["contents"][0]["parts"][0]["text"])
        self.assertIn("systemInstruction", body)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")

    def test_schema_is_requested_through_instructions(self) -> None:
        provider, seen = provider_with(gemini_text("{}"))
        structured = LLMRequest(
            operation="generate_structured",
            system="Return JSON.",
            user="answer",
            params={"schema": {"type": "object", "required": ["answer"]}},
        )
        provider.complete(structured)
        system_text = seen["body"]["systemInstruction"]["parts"][0]["text"]
        self.assertIn("JSON schema", system_text)
        self.assertIn("required", system_text)

    def test_request_timeout_is_forwarded(self) -> None:
        provider, seen = provider_with(gemini_text("{}"))
        provider.complete(REQUEST)
        self.assertEqual(seen["timeout"], 5.0)

    def test_user_prompt_is_bounded_before_leaving_the_process(self) -> None:
        long_request = LLMRequest(
            operation="understand",
            system="s",
            user="x" * 40_000,
            params={"corpus": "x" * 40_000},
        )
        provider, seen = provider_with(gemini_text("{}"))
        provider.complete(long_request)
        sent = seen["body"]["contents"][0]["parts"][0]["text"]
        self.assertEqual(len(sent), 32_000)

    def test_short_prompt_is_forwarded_verbatim(self) -> None:
        provider, seen = provider_with(gemini_text("{}"))
        provider.complete(REQUEST)
        self.assertEqual(
            seen["body"]["contents"][0]["parts"][0]["text"],
            "Interpret: the parser crashes on empty input",
        )


class GeminiResponseTranslationTests(unittest.TestCase):
    def test_valid_response_is_returned_as_text(self) -> None:
        payload = gemini_text('{"intent": "debug", "entities": ["parser"], "topics": ["bug"],'
                              ' "salience": 0.6, "confidence": 0.8, "summary": "s",'
                              ' "relevant_code_concepts": ["parse"]}')
        provider, _ = provider_with(payload)
        text = provider.complete(REQUEST)
        self.assertEqual(json.loads(text)["intent"], "debug")

    def test_empty_candidates_is_invalid_output(self) -> None:
        provider, _ = provider_with({"candidates": []})
        with self.assertRaises(InvalidLLMOutputError):
            provider.complete(REQUEST)

    def test_no_text_parts_is_invalid_output(self) -> None:
        provider, _ = provider_with({"candidates": [{"content": {"parts": []}}]})
        with self.assertRaises(InvalidLLMOutputError):
            provider.complete(REQUEST)

    def test_valid_json_without_gemini_envelope_is_invalid_output(self) -> None:
        provider, _ = provider_with({"unexpected": True})
        with self.assertRaises(InvalidLLMOutputError):
            provider.complete(REQUEST)

    def test_non_json_body_is_a_provider_error(self) -> None:
        class RawResponse(FakeResponse):
            def __init__(self) -> None:  # type: ignore[no-untyped-def]
                self._body = b"<html>not json</html>"
                self.status = 200

        def opener(request, timeout=None):  # type: ignore[no-untyped-def]
            return RawResponse()

        cfg = GeminiConfig(api_key="k", enabled=True)
        provider = GeminiProvider(cfg, opener=opener)
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("non-JSON", str(caught.exception))


class GeminiFailureTests(unittest.TestCase):
    def test_rate_limit_is_a_typed_provider_error(self) -> None:
        error = urllib.error.HTTPError(
            "u", 429, "Too Many Requests", {}, io.BytesIO(b'{"error":"quota"}')
        )
        provider, _ = provider_with({}, error=error)
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("rate limit", str(caught.exception))

    def test_auth_failure_does_not_leak_provider_payload(self) -> None:
        error = urllib.error.HTTPError(
            "u", 401, "Unauthorized", {}, io.BytesIO(b'{"error":{"message":"bad key abc"}}')
        )
        provider, _ = provider_with({}, error=error)
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        message = str(caught.exception)
        self.assertIn("authentication failed", message)
        self.assertNotIn("bad key abc", message)

    def test_server_error_is_typed(self) -> None:
        error = urllib.error.HTTPError("u", 503, "Unavailable", {}, io.BytesIO(b""))
        provider, _ = provider_with({}, error=error)
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("server error", str(caught.exception))

    def test_timeout_is_typed(self) -> None:
        provider, _ = provider_with({}, error=TimeoutError("timed out"))
        with self.assertRaises(LLMTimeoutError):
            provider.complete(REQUEST)

    def test_network_failure_is_typed(self) -> None:
        provider, _ = provider_with(
            {}, error=urllib.error.URLError("connection refused")
        )
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("connection refused", str(caught.exception))

    def test_safety_block_is_reported_without_inventing_output(self) -> None:
        provider, _ = provider_with(
            {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}
        )
        with self.assertRaises(LLMProviderError) as caught:
            provider.complete(REQUEST)
        self.assertIn("SAFETY", str(caught.exception))

    def test_usage_counters_track_failures(self) -> None:
        provider, _ = provider_with({}, error=urllib.error.HTTPError("u", 500, "e", {}, io.BytesIO(b"")))
        with self.assertRaises(LLMProviderError):
            provider.complete(REQUEST)
        self.assertEqual(provider.usage.request_count, 1)
        self.assertEqual(provider.usage.failure_count, 1)
        self.assertEqual(provider.usage.success_count, 0)


class GeminiGatewayIntegrationTests(unittest.TestCase):
    def test_gateway_uses_gemini_result_on_success(self) -> None:
        payload = gemini_text(
            '{"intent": "debug", "entities": ["parser"], "topics": ["bug"],'
            ' "salience": 0.7, "confidence": 0.9, "summary": "Parser bug",'
            ' "relevant_code_concepts": ["parse"]}'
        )
        provider, _ = provider_with(payload)
        gateway = LLMGateway(provider, fallback=HeuristicProvider(), timeout_seconds=5.0)
        result = gateway.understand("the parser crashes on empty input")
        self.assertIsInstance(result, UnderstandingResult)
        self.assertEqual(result.provider, "gemini")
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.summary, "Parser bug")

    def test_gateway_falls_back_when_gemini_fails(self) -> None:
        error = urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b""))
        provider, _ = provider_with({}, error=error)
        gateway = LLMGateway(provider, fallback=HeuristicProvider(), timeout_seconds=5.0)
        result = gateway.understand("the parser crashes on empty input")
        self.assertEqual(result.provider, "heuristic")
        self.assertTrue(result.fallback_used)

    def test_gateway_falls_back_on_malformed_output(self) -> None:
        provider, _ = provider_with(gemini_text("not json at all"))
        gateway = LLMGateway(provider, fallback=HeuristicProvider(), timeout_seconds=5.0)
        result = gateway.understand("the parser crashes on empty input")
        self.assertTrue(result.fallback_used)

    def test_gateway_falls_back_when_gemini_is_disabled(self) -> None:
        disabled = GeminiConfig(api_key="", enabled=False)
        provider = GeminiProvider(disabled, opener=lambda *a, **k: None)
        gateway = LLMGateway(provider, fallback=HeuristicProvider(), timeout_seconds=5.0)
        result = gateway.understand("the parser crashes")
        self.assertEqual(result.provider, "heuristic")
        self.assertTrue(result.fallback_used)

    def test_offline_default_gateway_is_untouched(self) -> None:
        gateway = build_gateway()
        self.assertEqual(gateway.provider.name, "heuristic")
        result = gateway.understand("the parser crashes on empty input")
        self.assertEqual(result.provider, "heuristic")


if __name__ == "__main__":
    unittest.main()
