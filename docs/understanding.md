# Understanding — LLM Gateway (Phase 3)

Provider-independent LLM access for Core Brain, plus validated structured
interpretation of developer text/code. Raw LLM output never flows anywhere in
an unvalidated form — everything is validated into pydantic models here.

## Public API

```python
from core import build_gateway, DeveloperContext

gateway = build_gateway()                    # default: heuristic (offline, deterministic)

result = gateway.understand("fix the null deref in user.email", user_id="usr_1")
# -> UnderstandingResult (entities, intent, topics, salience, confidence, summary,...)

analysis = gateway.analyze(DeveloperContext(...))     # -> DeveloperAnalysis
review = gateway.generate_structured(MySchema, system="...", user="...")  # -> MySchema
```

## LLMGateway

```
LLMGateway
├── understand(corpus)             -> validated UnderstandingResult
├── analyze(developer_context)     -> validated DeveloperAnalysis (trusted stats)
└── generate_structured(schema, ...) -> validated instance (never silent fallback)
```

- **Timeout** — providers receive `LLMRequest.timeout_seconds`; a provider that
  exceeds it raises `LLMTimeoutError`.
- **Errors** — structured hierarchy in `core/understanding/exceptions.py`:
  `UnderstandingError` → `LLMGatewayError` → `LLMTimeoutError` /
  `LLMProviderError` / `InvalidLLMOutputError`.
- **Invalid structured output** — every provider response is funnelled through
  `core/understanding/validation.py` (strict JSON + pydantic validation).
- **Provider abstraction** — a provider is just a text-completion port
  (`LLMProvider.name` + `LLMProvider.complete(request)`). Real providers
  (OpenAI/Anthropic/local) register behind it via `register_provider(...)`.
- **Deterministic fallback** — `understand`/`analyze` retry with the heuristic
  provider on timeout / provider failure / malformed output. The result is
  stamped `fallback_used=True` so callers know it is heuristic-quality.
  `generate_structured` NEVER silently falls back (no fabricated certainty).

## Provider selection

`GatewayConfig(provider=..., fallback_provider=..., timeout_seconds=...)` +
`build_gateway(config)`. Names are registered in `providers.py`; the default
provider is **`heuristic`** — deterministic and offline, so the MVP runs
without an API key and the end-to-end demo is fully reproducible.

## The heuristic provider

`HeuristicProvider` cannot be wrong: it emits low, honest confidence and
keyword-derived intent/topics/salience. It is deliberately conservative:

- `confidence = 0.2` always (keyword heuristics ≠ AI), no fake certainty.
- intent via keyword buckets (`debug`, `explain`, `review`, `implement`,
  `deploy`, else `understand`).
- entities / `relevant_code_concepts` from identifier frequency.
- topics from a fixed vocabulary (bug, error, test, api, auth, database,
  performance, security, deploy, refactor).

## Structured results

- `UnderstandingResult` — validated, `extra="forbid"`; envelope fields
  (`provider`, `fallback_used`, `user_id`, `corpus_id`) are stamped by the
  gateway from trusted inputs, never from provider output.
- `DeveloperAnalysis` — wraps the corpus `UnderstandingResult` with trusted
  statistics computed from `DeveloperContext`: `files_analyzed`, `total_lines`,
  `languages`, `focus_file`, `focus_line`, `confidence`.
- Nothing is written to Memory by this phase. Any future persistence of these
  results must go through validation (this module) first.

## DeveloperContext (input)

Transport-independent repository/code context supplied by the Product layer:
`user_id`, `repository`, `files[]`, `changed_files[]`, `current_file`,
`current_line`, `git_context`, `test_results[]`, `user_context`. No IDE / editor
/ transport assumptions.

## Isolation

`analyze` stamps `user_id` and `repository` from the **trusted**
`DeveloperContext`; values in provider output (even a spoofed `user_id`) never
override them. Correlated searches/memories stay scoped to the user/project.

## Error handling

Failures are explicit, never silent-success: a provider timeout/outage/malformed
output either resolves via the deterministic fallback (marked in the result) or
raises a structured `LLMGatewayError` subclass.