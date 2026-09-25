# Digital Brain — TypeScript Client (Phase 8, Slice 6)

A thin, framework-free client for the Digital Brain API v1. It speaks the two
transport surfaces the Core already exposes and adds nothing else: no UI, no
state store, no retry/replay queue, no authentication, no action execution.

```ts
import { HttpBrainClient, WebSocketBrainClient } from "digital-brain-client";

const http = new HttpBrainClient({ baseUrl: "http://127.0.0.1:8765", userId: "usr_ali" });
const timeline = await http.call("people_timeline", { person_id: "per_ali" });
```

The same source runs unchanged in a browser, in a React Native app and in Node
22+: `src/` imports nothing but its own relative modules and uses only the
platform globals `fetch`, `WebSocket`, `AbortController`, `setTimeout` and
`TextDecoder`. A test enforces that boundary.

## What it is

| | |
|---|---|
| Runtime dependencies | none |
| `HttpBrainClient` | `POST {baseUrl}/v1/brain` + `GET {baseUrl}/health` |
| `WebSocketBrainClient` | `{wsBase}/v1/brain?user_id=…`, response **and** event frames |
| Typed surface | all 17 v1 methods, params and results |
| Errors | `BrainApiError` / `BrainTransportError` / `BrainContractError` |

The HTTP transport bundled with the Core wires `NullEventSink`, so it has no
event stream. `HttpBrainClient.supportsEvents` is `false`; use
`WebSocketBrainClient` for live Brain events.

## Two ways to call

```ts
const result = await client.call("preferences");            // typed result, throws on ok=false
const envelope = await client.request("preferences");       // full ApiResponse, ok=false is data
```

`call()` returns the typed result and throws `BrainApiError` for a typed Brain
failure. `request()` never throws for `ok=false`, so a UI can render the error
inline. Both throw `BrainTransportError` when no valid `ApiResponse` came back
at all (network failure, timeout, non-JSON body, wrong endpoint).

Branch on `error.code`, never on an HTTP status — the status is transport
metadata only.

## Identity

`userId` is the caller's identity. It is injected into the params of every
method that carries a top-level `user_id`, and on a WebSocket connection it is
also the `user_id` query that routes events.

```ts
const client = new WebSocketBrainClient({ url: "ws://127.0.0.1:8766", userId: "usr_ali" });
```

A `params.user_id` that disagrees with the configured identity is refused
locally instead of being sent and rejected by the server. The identity query is
**routing and isolation metadata, not authentication** — add real auth and TLS
at the deployment boundary.

## Events

```ts
const stop = client.onEvent((event) => {
  console.log(event.type, client.correlationIdOf(event));
});
```

The client implements the consumer rules from `docs/event-delivery.md`:

- at-most-once delivery, deduplicated by `BrainEvent.id` (bounded window, 1024 by default);
- every event filtered by the connection `user_id` before any handler sees it;
- per-operation FIFO order; events emitted by a request arrive before its response;
- `correlationIdOf(event)` reads `payload.correlation_id` for grouping;
- malformed or unknown frames are counted in `client.stats` and ignored, never thrown;
- **no** replay, retry or reconnect recovery: events lost to a disconnect or a
  bounded server buffer are gone. Do not build UI state that assumes otherwise.

## One outstanding request

The Core WebSocket adapter processes one request at a time per connection.
`WebSocketBrainClient` therefore serializes calls on an internal queue, so
concurrent `await` calls are safe:

```ts
const [a, b] = await Promise.all([client.call("ping"), client.call("preferences")]);
```

## Types and the schema

`src/contract.ts` mirrors `contracts/schemas/brain-api.v1.json`. The runtime
tables (`API_METHODS`, `API_ERROR_CODES`) are compared against that artifact by
`test/contract.test.ts`, so a new Core method that is not mirrored here fails
the suite instead of drifting silently.

Payloads the Core contract keeps open — `BrainEvent.payload`, and the
`understand` / `reason` analyses — are typed as `unknown` or open records
rather than guessed into closed shapes.

## Running the tests

No install step is required. Node 22.6+ executes the TypeScript sources
directly:

```bash
cd clients/typescript
node --test test/
```

The suite has three layers:

| file | what it covers |
|---|---|
| `test/contract.test.ts` | method/error-code/definition parity with the schema artifact, `src/` architecture boundary |
| `test/http.test.ts` | **live** end-to-end against the real Core HTTP transport (`python -m core.transport.http`, in-memory DB) |
| `test/websocket.test.ts` | client protocol logic against an in-memory socket double |
| `test/websocket-live.test.ts` | the real platform `WebSocket` against a real socket, using a minimal RFC 6455 test fixture |

`npm test` runs the same `node --test test/`.

### Type checking

`tsconfig.json` is strict, and the sources are written in *erasable* TypeScript
so Node can run them without a build step. Full type checking needs the
TypeScript compiler, which is declared as a devDependency but is not installed
in this repository's environment:

```bash
npm install        # devDependencies only: typescript, @types/node
npm run typecheck  # tsc -p tsconfig.json  (src/ only)
```

Without that install, the suite still verifies runtime behaviour, wire
compatibility with the real Core server and schema parity — but not static
types.

## Out of scope

Durable delivery, retries, acknowledgements, a broker, auth sessions,
notifications/push, audio capture, and any rendering. Those belong to Product,
and the Brain only ever *proposes* actions.
