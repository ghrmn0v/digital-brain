# Gemini Provider + Long-Term Learning (Phase 9, Slice 1)

Gemini is the Brain's **reasoning component**. The Brain stays the layer that
remembers the user:

```text
Gemini does NOT remember the user.
Digital Brain remembers the user.
```

Each request carries only the context the Brain selected for that request.
Nothing new was invented to make this work — the existing architecture already
had every piece:

```text
existing LLMProvider port  ->  GeminiProvider        (new, one implementation)
existing provider registry ->  register "gemini"     (new, one entry)
existing LLMGateway        ->  unchanged (selection, validation, fallback)
existing SemanticSearch    ->  relevant memories     (unchanged)
existing PeopleIntelligence -> preferences, people   (unchanged)
existing LearningEngine   ->  evidence + learning    (unchanged)
```

## What was added

| File | Role |
|---|---|
| `core/understanding/gemini.py` | `GeminiConfig` + `GeminiProvider` behind the existing `LLMProvider` port |
| `core/context/personalization.py` | bounded, user-scoped Brain context + prompt rendering |
| `core/learning/candidates.py` | provider suggestion → candidate → existing learning/preference paths |
| `core/service/brain_service.py` | `personalized_insight()` (service level, **no new API method**) |
| `scripts/gemini_learning_demo.py` | deterministic 4-interaction learning demonstration |
| `tests/test_gemini_provider.py` | provider, configuration, failure and gateway tests (30) |
| `tests/test_personalized_brain.py` | context, learning, precedence and personalization tests (27) |

The public v1 API is unchanged: no new `ApiMethod`, no schema change, no client
change. `personalized_insight` is a service-level capability, so nothing that
already consumed the Brain API can regress.

## Configuration

The Brain has no other configuration source, so the provider reads the
environment lazily (nothing at import time):

```env
GEMINI_API_KEY=...            # never hardcoded, never logged
GEMINI_MODEL=gemini-3.8-flash # model is configuration, not code
GEMINI_ENABLED=true           # explicit opt-in
GEMINI_API_BASE=https://generativelanguage.googleapis.com
GEMINI_TIMEOUT_SECONDS=30
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=2048
```

Select it through the existing selection path:

```python
from core.understanding import GatewayConfig, build_gateway

gateway = build_gateway(GatewayConfig(provider="gemini", fallback_provider="heuristic"))
```

## Context assembly (the part that matters)

```text
user input
  -> identify the user
  -> relevant memories       (SemanticSearch, user-scoped, top_k bounded)
  -> relevant preferences    (People Intelligence, relevance-scored)
  -> mentioned people        (People Intelligence.identify_people)
  -> learned evidence        (Learning Engine status)
  -> bounded context + labelled prompt
  -> provider
```

Guarantees, all test-covered:

* **Bounded** — every list capped, every statement truncated (300 chars), the
  user prompt truncated to 32 000 characters before it leaves the process. There
  is no code path that serializes the whole store.
* **Relevance-filtered** — an unrelated memory, person or topic is not included
  just because it exists.
* **User-scoped** — every read is filtered by the request's `user_id`.
* **Labelled** — explicit statements, learned evidence and provider inferences
  are marked differently, so a model cannot present a weak signal as a fact.

## Learning: a model answer is never a fact

`route_candidates` applies a deliberately conservative split:

| candidate evidence | routed to | effect |
|---|---|---|
| `explicit_user_statement` | `PeopleIntelligence.record_preference` | stored immediately, with provenance |
| `repeated_acceptance` / `repeated_rejection` | `LearningEngine.record_feedback` | counted evidence; becomes a preference only past the existing threshold |
| `inference` | nowhere | rejected with a reason |

Explicit-over-learned precedence is therefore *structural*, not re-implemented:
an explicit preference owns its `<domain>:<name>` conflict key, and the
Learning Engine's `_has_explicit_preference` policy then blocks any learned
write for the same key. Both behaviours are regression-tested.

The provider cannot write memory. It returns text; the gateway validates it
into a Brain model; only the Brain's own subsystems persist anything.
`target_event_id` is required, so a candidate can never be learned from an
invented anchor.

## Failure and fallback

Provider failure never breaks the Brain:

| failure | existing typed error | result |
|---|---|---|
| disabled / no key | `LLMProviderError` | gateway fallback (`understand`/`analyze`) or context-only answer (`personalized_insight`) |
| timeout | `LLMTimeoutError` | same |
| rate limit (429) | `LLMProviderError` | same |
| auth (401/403) | `LLMProviderError` (payload never echoed) | same |
| 5xx | `LLMProviderError` | same |
| safety block | `LLMProviderError` | same |
| empty/invalid output | `InvalidLLMOutputError` | same |

Credentials never leave the provider: not in a prompt, a result, an event, a log
line or an error message. `GeminiConfig.redacted()` is the only shape intended
for diagnostics.

## Demo

```bash
python scripts/gemini_learning_demo.py
```

Four interactions against a local stand-in for the Gemini endpoint (the provider
performs real HTTP; only Google's server is absent, so the reply is scripted):

1. the user states a preference → stored as an explicit preference;
2. a related question → answered from the retrieved, labelled context;
3. the user changes the preference → the new explicit value supersedes;
4. asking again → the new value is used.

This proves *the Digital Brain learned*, not that the model did.

## Real Gemini API

Not exercised in this environment: no `GEMINI_API_KEY` is present, so the real
endpoint was never called. What **was** verified is the request shape against
the published Gemini REST contract (`POST /v1beta/models/{model}:generateContent`,
`x-goog-api-key` header, `contents` / `systemInstruction` /
`generationConfig.responseMimeType`), and the full provider path against a real
HTTP server locally.

To run it for real:

```bash
export GEMINI_API_KEY=...            # keep it in your shell / secret store
export GEMINI_ENABLED=true
export GEMINI_MODEL=gemini-3.8-flash
python scripts/gemini_learning_demo.py   # then edit the script to use the real base URL
```

A key mismatch, timeout or quota error falls back exactly as the table above
describes, so a demo degrades instead of breaking.

## Limitations

* No streaming, tool calling, embeddings or batch mode.
* Structured output is requested through instructions, not Gemini's
  `responseJsonSchema`, because that field accepts only a JSON Schema subset and
  a rejected schema would fail the whole request. The gateway validates
  strictly either way.
* `personalized_insight` is not exposed as an API method on purpose: adding one
  would change the v1 contract, the canonical schema and both clients.
* Cost/latency budgeting beyond the per-request timeout is not implemented.
