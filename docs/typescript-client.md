# TypeScript Client (Phase 8, Slice 6)

`clients/typescript/` is a thin, framework-free client for the API v1 contract.
It is a **Product-side** artifact: Core publishes the contract, the client
consumes it and never re-implements Brain behaviour.

```text
Product UI / service
  -> HttpBrainClient   or   WebSocketBrainClient     (clients/typescript)
  -> POST /v1/brain            ws://…/v1/brain?user_id=…
  -> core/transport/http.py    core/transport/websocket.py
  -> BrainApi -> BrainService -> Core Brain
```

The client contains no Brain logic: no scoring, no classification, no conflict
resolution, no retries. It builds the canonical envelopes, correlates responses,
applies the documented consumer rules for events, and surfaces the existing
`ApiError` codes.

## Scope

| Concern | Owner |
|---|---|
| `ApiRequest`/`ApiResponse` construction, id minting | client |
| Canonical `ApiError` mapping to typed exceptions | client |
| Event dedupe by `BrainEvent.id`, `user_id` filter, ordering | client |
| Live event stream (WebSocket) | Core adapter |
| Memory, people, reasoning, planning, execution | Core / Product |

## Transports

`HttpBrainClient` — `POST {baseUrl}/v1/brain` per call, plus the static
`GET {baseUrl}/health` probe. The Core HTTP CLI wires `NullEventSink`, so this
client is request/response only and reports `supportsEvents === false`.

`WebSocketBrainClient` — one connection to `{wsBase}/v1/brain?user_id=…`.
Requests are serialized because the Core adapter allows one outstanding
response per connection; concurrent `await` calls are therefore safe.

Both use only platform globals (`fetch`, `WebSocket`, `AbortController`,
`setTimeout`, `TextDecoder`) and import nothing but their own relative modules.
The same source runs in a browser, a React Native app and Node 22+, which is
what "one Core Brain, two clients" requires. A test enforces that boundary.

## Contract fidelity

`src/contract.ts` mirrors `contracts/schemas/brain-api.v1.json`: all 17 methods,
their params and results, the `ApiErrorCode` enum and the frame envelopes.
`test/contract.test.ts` asserts the runtime tables against the checked-in
artifact — method order, params/result `$defs` names and error codes — so an
unmirrored additive Core change fails the suite instead of drifting silently.
Full static type checking (`tsc`) needs the TypeScript devDependency and is
declared in `package.json`; see the client README.

## Consumer rules the client implements

- branch on `ApiError.code`, never on the HTTP status;
- deduplicate events by `BrainEvent.id` (bounded window);
- filter events by `user_id` before processing;
- group by `payload.correlation_id` (`client.correlationIdOf(event)`);
- preserve per-operation order; do not invent global ordering;
- treat delivery as at-most-once and best-effort: no replay after reconnect;
- `user_id` is routing/isolation metadata, not authentication.

## Verification

```bash
cd clients/typescript
node --test test/
```

- `contract.test.ts` — schema parity and the `src/` architecture boundary.
- `http.test.ts` — **live** end-to-end against the real Core HTTP transport
  (real server, in-memory DB): health, ping, describe, ingest, preferences,
  `people_timeline` with provenance, per-user isolation, canonical error codes,
  timeouts, non-Brain endpoints.
- `websocket.test.ts` — client protocol logic against an in-memory socket
  double: identity admission, request serialization, id correlation, event
  ordering/dedupe/filtering, malformed frames, timeouts, close handling.
- `websocket-live.test.ts` — the real platform `WebSocket` over a real TCP
  socket using a minimal RFC 6455 test fixture in `test/support/`.

That last layer exists because the Core WebSocket adapter needs the
`websockets` package, which is not installed in this environment. The fixture
is a test double, not a Brain: it proves the client half of the protocol, while
the adapter's own semantics stay covered by `tests/test_websocket_transport.py`.
