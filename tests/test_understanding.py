"""Phase 3 — LLM Gateway + Understanding tests.

Covers: valid responses, malformed output, timeout/provider failure, fallback,
structured validation, context analysis, user isolation, determinism.
"""

import unittest

from pydantic import BaseModel, ConfigDict, Field
from contracts.memory.memory import MemoryType

from core.understanding import (
    DeveloperContext,
    GatewayConfig,
    HeuristicProvider,
    InvalidLLMOutputError,
    LLMGateway,
    LLMGatewayError,
    LLMProviderError,
    LLMTimeoutError,
    UnderstandingError,
    UnderstandingIntent,
    UnderstandingResult,
    build_gateway,
    create_provider,
    register_provider,
)

from .understanding_support import (
    ProviderFailureProvider,
    RecordingProvider,
    ReturningProvider,
    TimeoutProvider,
    valid_understanding,
)


def make_context(user_id="usr_1", repository="demo-repo", **kw) -> DeveloperContext:
    data = {
        "user_id": user_id,
        "repository": repository,
        "files": [
            {
                "path": "src/login.ts",
                "content": (
                    "function getUser() { return undefined }\n"
                    "export function getEmail() { return getUser().email }\n"
                    "// TODO handle null\n"
                ),
                "language": "typescript",
            },
            {"path": "src/util.ts", "content": "export const id = 1\n"},
        ],
        "changed_files": ["src/login.ts"],
        "current_file": "src/login.ts",
        "current_line": 3,
        "git_context": {"branch": "main"},
    }
    data.update(kw)
    return DeveloperContext(**data)


class TestLLMGatewayValid(unittest.TestCase):
    def test_valid_response_parsed(self):
        provider = ReturningProvider(valid_understanding())
        gateway = LLMGateway(provider)
        result = gateway.understand(
            "user bug", user_id="usr_1", corpus_id="corp_1"
        )
        self.assertIsInstance(result, UnderstandingResult)
        self.assertEqual(result.provider, "stub-return")
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.user_id, "usr_1")
        self.assertEqual(result.corpus_id, "corp_1")
        self.assertEqual(result.intent, UnderstandingIntent.DEBUG)
        self.assertEqual(result.entities, ["user", "email"])
        self.assertEqual(result.confidence, 0.7)
        self.assertEqual(
            result.summary, "Possible null reference on user.email."
        )

    def test_request_carries_corpus_and_timeout(self):
        provider = RecordingProvider(valid_understanding())
        gateway = LLMGateway(provider, timeout_seconds=11.0)
        gateway.understand("x")
        request = provider.requests[0]
        self.assertEqual(request.operation, "understand")
        self.assertEqual(request.timeout_seconds, 11.0)
        self.assertEqual(request.params["corpus"], "x")

    def test_empty_corpus_rejected(self):
        gateway = LLMGateway(ReturningProvider(valid_understanding()))
        with self.assertRaises(UnderstandingError):
            gateway.understand("   ")


class TestLLGFallback(unittest.TestCase):
    def test_malformed_json_falls_back(self):
        primary = ReturningProvider("this is not json")
        fallback = HeuristicProvider()
        gateway = LLMGateway(primary, fallback=fallback)
        result = gateway.understand("a bug in user.email")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.provider, "heuristic")
        self.assertEqual(result.intent, UnderstandingIntent.DEBUG)

    def test_schema_invalid_falls_back(self):
        primary = ReturningProvider(valid_understanding(confidence=5.0))
        gateway = LLMGateway(primary, fallback=HeuristicProvider())
        result = gateway.understand("a bug in user.email")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.confidence, 0.2)  # heuristic's honest low value

    def test_timeout_falls_back(self):
        gateway = LLMGateway(TimeoutProvider(), fallback=HeuristicProvider())
        result = gateway.understand("bug")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.provider, "heuristic")

    def test_provider_failure_falls_back(self):
        gateway = LLMGateway(ProviderFailureProvider(), fallback=HeuristicProvider())
        result = gateway.understand("bug")
        self.assertTrue(result.fallback_used)

    def test_no_fallback_reraises_timeout(self):
        gateway = LLMGateway(TimeoutProvider())
        with self.assertRaises(LLMTimeoutError):
            gateway.understand("bug")

    def test_no_fallback_reraises_invalid_output(self):
        gateway = LLMGateway(ReturningProvider("garbage"))
        with self.assertRaises(InvalidLLMOutputError):
            gateway.understand("bug")

    def test_fallback_also_failing_lifts_error(self):
        gateway = LLMGateway(
            ProviderFailureProvider(), fallback=ProviderFailureProvider()
        )
        with self.assertRaises(LLMGatewayError):
            gateway.understand("bug")

    def test_default_gateway_works_offline(self):
        gateway = build_gateway()
        result = gateway.understand("undefined is not a function")
        self.assertEqual(result.provider, "heuristic")
        self.assertFalse(result.fallback_used)


class TestGenerateStructured(unittest.TestCase):
    class Result(BaseModel):
        model_config = ConfigDict(extra="forbid")
        verdict: str
        score: float = Field(ge=0, le=10)

    def test_valid_structured_output(self):
        provider = ReturningProvider('{"verdict": "ok", "score": 7}')
        gateway = LLMGateway(provider)
        result = gateway.generate_structured(
            TestGenerateStructured.Result, system="s", user="u"
        )
        self.assertEqual(result.verdict, "ok")
        self.assertEqual(result.score, 7)

    def test_malformed_structured_output_raises(self):
        gateway = LLMGateway(ReturningProvider("not json at all"))
        with self.assertRaises(InvalidLLMOutputError):
            gateway.generate_structured(TestGenerateStructured.Result, system="s", user="u")

    def test_out_of_range_raises(self):
        gateway = LLMGateway(ReturningProvider('{"verdict": "x", "score": 99}'))
        with self.assertRaises(InvalidLLMOutputError):
            gateway.generate_structured(TestGenerateStructured.Result, system="s", user="u")

    def test_no_silent_fallback_even_with_fallback_configured(self):
        gateway = LLMGateway(
            ReturningProvider("garbage"), fallback=HeuristicProvider()
        )
        with self.assertRaises(InvalidLLMOutputError):
            gateway.generate_structured(TestGenerateStructured.Result, system="s", user="u")


class TestAnalyze(unittest.TestCase):
    def test_context_stats_and_focus_preserved(self):
        provider = RecordingProvider(valid_understanding())
        gateway = LLMGateway(provider)
        analysis = gateway.analyze(make_context())
        self.assertEqual(analysis.repository, "demo-repo")
        self.assertEqual(analysis.user_id, "usr_1")
        self.assertEqual(analysis.files_analyzed, 2)
        self.assertEqual(analysis.total_lines, 6)
        self.assertEqual(analysis.languages, ["typescript"])
        self.assertEqual(analysis.focus_file, "src/login.ts")
        self.assertEqual(analysis.focus_line, 3)
        self.assertEqual(analysis.confidence, 0.7)
        self.assertEqual(analysis.understanding.intent, UnderstandingIntent.DEBUG)

    def test_llm_cannot_override_trusted_user_id(self):
        provider = ReturningProvider(valid_understanding(user_id="evil"))
        gateway = LLMGateway(provider)
        analysis = gateway.analyze(make_context(user_id="usr_actual"))
        self.assertEqual(analysis.user_id, "usr_actual")
        self.assertEqual(analysis.understanding.user_id, "usr_actual")

    def test_analyze_sends_changed_files_as_corpus(self):
        provider = RecordingProvider(valid_understanding())
        LLMGateway(provider).analyze(make_context())
        corpus = provider.requests[0].params["corpus"]
        self.assertIn("getUser", corpus)
        self.assertIn("src/login.ts", corpus)
        self.assertNotIn("src/util.ts", corpus)  # not changed/current

    def test_user_isolation_no_leak(self):
        gateway = LLMGateway(HeuristicProvider())
        a = gateway.analyze(make_context(user_id="usr_a", repository="repo-a"))
        b = gateway.analyze(make_context(user_id="usr_b", repository="repo-b"))
        self.assertEqual(a.user_id, "usr_a")
        self.assertEqual(b.user_id, "usr_b")
        self.assertEqual(a.repository, "repo-a")
        self.assertEqual(b.repository, "repo-b")
        self.assertEqual(a.understanding.user_id, "usr_a")
        self.assertEqual(b.understanding.user_id, "usr_b")


class TestProviderSelection(unittest.TestCase):
    def test_unknown_provider_raises(self):
        with self.assertRaises(LLMProviderError):
            build_gateway(GatewayConfig(provider="nope-provider"))

    def test_registered_provider_selectable(self):
        register_provider(
            "custom-hello",
            lambda: ReturningProvider(valid_understanding(), name="custom-hello"),
        )
        gateway = build_gateway(GatewayConfig(provider="custom-hello"))
        result = gateway.understand("hello")
        self.assertEqual(result.provider, "custom-hello")

    def test_heuristic_is_an_llm_provider(self):
        from core.understanding.providers import LLMProvider

        self.assertIsInstance(HeuristicProvider(), LLMProvider)
        self.assertIsInstance(create_provider("heuristic"), LLMProvider)

    def test_heuristic_deterministic(self):
        gateway_a = build_gateway()
        gateway_b = build_gateway()
        corpus = "checkout fast bug: null deref in user.email; add a test"
        self.assertEqual(
            gateway_a.understand(corpus).model_dump(),
            gateway_b.understand(corpus).model_dump(),
        )


if __name__ == "__main__":
    unittest.main()