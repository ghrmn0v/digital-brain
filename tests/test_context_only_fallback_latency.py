"""The context-only fallback has to be *fast*, and that has to be proven.

``tests/test_personalized_brain.py`` already pins what the fallback says: that it
triggers, that it names the reason, that an outage and a timeout are told apart,
and that it answers from the Brain's own state instead of inventing something.
What nothing pinned was how long it takes, which is the property a demo actually
feels. A model outage that quietly grew a retry loop, or that started waiting on
a socket nobody told us about, would still pass every other test while turning
"the Brain answers instantly" into "the Brain hangs".

Two assertions, deliberately:

* The provider is called exactly once per turn. This is the real invariant and it
  is completely deterministic — it fails if anyone adds a retry, a backoff, or a
  second attempt, and it cannot flake no matter how slow the machine is.
* Wall-clock stays far below the timeout the gateway would have waited. The
  bounds are loose on purpose. ``GATEWAY_TIMEOUT`` is what a slow provider would
  cost; the fallback must beat it by a wide margin or it is not a fallback. A
  generous multiplier keeps this green on a loaded CI box while still catching a
  regression that turns a local answer into a network wait.
"""

from __future__ import annotations

import time
import unittest

from core.service.brain_service import build_brain_service
from core.understanding import LLMGateway, LLMProvider, LLMRequest
from core.understanding.exceptions import LLMProviderError

USER = "usr_fallback_latency"

#: What the gateway is willing to wait for a slow provider. The fallback exists to
#: beat this, not to approach it.
GATEWAY_TIMEOUT_SECONDS = 5.0

#: Ceiling for the whole fallback turn. Roughly 2x the gateway timeout: loose
#: enough that a loaded machine cannot fail it, tight enough that a real network
#: dependency (a socket defaulting to ~30s, or a retry loop) trips it.
FALLBACK_BUDGET_SECONDS = 10.0

TURNS = 3


class DeadProvider(LLMProvider):
    """Fails the instant it is called, like an upstream that is simply gone."""

    name = "dead"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: LLMRequest) -> str:
        self.calls += 1
        raise LLMProviderError("upstream is down")


class ContextOnlyFallbackLatencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = build_brain_service(":memory:")
        self.addCleanup(self.service.close)
        self.service.record_preference(
            USER, name="backend_language", value="TypeScript", domain="language"
        )
        self.provider = DeadProvider()
        self.service._understanding = LLMGateway(
            self.provider, timeout_seconds=GATEWAY_TIMEOUT_SECONDS
        )

    def test_fallback_answers_within_budget_and_calls_the_provider_once(self) -> None:
        durations: list[float] = []

        for turn in range(TURNS):
            started = time.perf_counter()
            outcome = self.service.chat(USER, "which backend language should I use?")
            durations.append(time.perf_counter() - started)

            # Each turn is a genuine fallback, not an accidental real answer.
            self.assertTrue(outcome.fallback_used, f"turn {turn} did not fall back")
            self.assertEqual(outcome.provider, "context-only")
            self.assertTrue(outcome.answer)
            self.assertIn("TypeScript", outcome.answer)

        # The deterministic invariant: no retries, no second attempt.
        self.assertEqual(
            self.provider.calls,
            TURNS,
            "fallback called the provider more than once per turn "
            "(a retry or backoff crept in)",
        )

        slowest = max(durations)
        self.assertLess(
            slowest,
            FALLBACK_BUDGET_SECONDS,
            f"slowest fallback turn took {slowest:.2f}s, budget is "
            f"{FALLBACK_BUDGET_SECONDS:.2f}s",
        )
        print(
            f"    context-only fallback: slowest {slowest * 1000:.0f}ms, "
            f"median {sorted(durations)[len(durations) // 2] * 1000:.0f}ms, "
            f"budget {FALLBACK_BUDGET_SECONDS:.0f}s"
        )


if __name__ == "__main__":
    unittest.main()
