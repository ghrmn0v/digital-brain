# Brain API v1 Schema Distribution (Phase 8 Slice 5A)

Digital Brain now publishes one deterministic, data-free JSON Schema artifact for
external clients:

```text
contracts/schemas/brain-api.v1.json
```

It is the offline counterpart of the runtime `describe` API. TypeScript and Java
generators can consume the same checked-in contract without importing Python,
starting `BrainService`, opening a socket or using `BrainApi`. The file is
included as `contracts.schemas` package data, so an installed wheel carries the
canonical artifact too.

## Source of truth

The contract layer owns all method-to-model metadata:

```text
contracts/api/registry.py
  ApiMethodSpec[]
  API_METHOD_REGISTRY
  api_method_names()
  describe_api_methods()
```

`ApiMethodSpec` binds each `ApiMethod` to exactly one typed parameter model and
one typed result model. The public registry is an immutable mapping and its
order is the stable v1 method order.

New methods are **appended**, never inserted: a later additive method (for
example `resolve_person`) must not renumber what a client already knows.

`BrainApi.describe()` calls `describe_api_methods()` from this registry. Its
method list and schemas therefore cannot drift into a private Core-only map.
Core keeps only the method-to-handler implementation map.

The stream wire envelopes also moved into the contract layer:

```text
contracts/api/frames.py
  ResponseEnvelope
  EventEnvelope
```

`core/transport/stdio.py` imports these canonical models, and the WebSocket
transport reuses the same `response_frame()` / `event_frame()` helpers. The wire
shape is unchanged:

```json
{"kind":"response","payload":{}}
{"kind":"event","payload":{}}
```

## Bundle structure

The generated artifact uses JSON Schema draft 2020-12 and has a stable URN:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:digital-brain:schema:brain-api:v1",
  "x-brain-api-version": "v1",
  "x-contracts": {},
  "x-methods": [],
  "$defs": {},
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

- `x-contracts` references `ApiRequest`, `ApiResponse`, `ApiError`,
  `ApiErrorCode`, `ApiMethod`, `BrainEvent`, `ResponseEnvelope` and
  `EventEnvelope`.
- `x-methods` is an ordered list. Every entry has `method`, a params `$ref` and
  a result `$ref`.
- `$defs` contains every referenced request, result, enum and nested contract.
  All `$ref` values resolve locally under `#/$defs/`.
- The root `type`/`properties`/`required` schema validates the catalog document
  itself; it is not a schema for an `ApiRequest` instance.
- `ResponseEnvelope.payload` remains the canonical generic `ApiResponse` XOR
  envelope. A generator gets the method-specific result type by pairing the
  response `method` with the same method's `x-methods[].result` reference.
- `BrainEvent.payload` remains an open object. Its documented event-specific
  shapes stay documentation/enums, not a guessed closed JSON Schema.

The file contains schemas only: no user ids, memories, events, timestamps,
database rows or service state.

## Generate and verify

From the repository root:

```bash
python -m contracts.api.schema
python -m contracts.api.schema --output contracts/schemas/brain-api.v1.json
```

After installing the Python package, the equivalent commands are:

```bash
digital-brain-export-schema --check
digital-brain-export-schema --output ./brain-api.v1.json
```

Generation requires an explicit output outside a source checkout; this avoids
writing into a read-only or shared `site-packages` directory.

A CI or pre-commit check can verify that the checked-in artifact has not drifted:

```bash
python -m contracts.api.schema --check
```

Serialization is deterministic:

- recursively sorted object keys;
- compact `,` / `:` separators;
- UTF-8 text;
- one trailing newline;
- no generation timestamp or machine-specific path.

The exact bytes are guaranteed for a given Pydantic generator version. Because
schema rendering can change between dependency releases, CI must run `--check`
after dependency updates and regenerate deliberately when the diff is reviewed.

`tests/test_api_schema_export.py` regenerates the bundle in memory and compares
it byte-for-byte with the checked-in file.

## Client generation and runtime behavior

A TS/Java generator should read the artifact as follows:

1. read `x-brain-api-version`; reject unsupported major versions;
2. iterate `x-methods` in declared order;
3. generate one typed request/result pair from each local `$ref`;
4. generate the shared request/response/error/event/frame contracts from
   `x-contracts`;
5. keep `ApiRequest.id` and branch on `ApiError.code` for request outcomes;
6. treat an unknown additive enum value as forward-compatible data according to
   the owning product's policy, never as a different user or action.

Runtime `describe` and the offline bundle intentionally differ in shape:
`describe` embeds each complete per-method schema for a live caller, while the
bundle centralizes shared definitions and references them. Both are produced
from the same public registry.

## Transport mapping for PC and Mobile clients

The schema does not prescribe UI, networking or device APIs.

| Client need | Existing protocol surface |
|---|---|
| Request/response only | HTTP `POST /v1/brain`; response is a bare `ApiResponse` |
| Request plus live events | WebSocket `/v1/brain?user_id=...`; response/event use `kind` frames |
| Local/wrapper process | stdio JSON-lines; one request per line, response/event frames |
| Developer intelligence | `analyze_developer` result and `developer.*` `BrainEvent` contracts |
| Normalized voice text | Product captures/transcribes audio, then sends text through `understand` |

Mobile code owns microphone capture, transcription UX, notifications, auth
sessions, APNs/FCM and screens. None of those belong in Core. The Brain proposes
actions; Product still executes them only after permission.

## Consumer rules that generated SDKs must preserve

- Deduplicate events by `BrainEvent.id`.
- Filter every event by `event.user_id` before processing it.
- Group related events by `payload["correlation_id"]`.
- Preserve per-operation stream order, but do not invent global ordering.
- Treat delivery as at-most-once and best-effort.
- Never assume reconnect or replay recovers events lost after disconnect or
  bounded-buffer overflow.
- Query-string `user_id` is routing/isolation metadata, not authentication.
  Deployment must add real authentication and TLS before untrusted access.
- HTTP status is transport metadata; clients branch on the canonical
  `ApiError.code` inside `ApiResponse`.

Durable queues, retries, acknowledgements, Redis/Kafka and push-provider
integrations are deliberately outside this schema slice.

## Versioning workflow

Follow `CONTRACTS.md`:

- additive optional field, new method, enum/event member or wider compatible
  payload stays v1;
- remove/rename a field, change a type/required set or change semantics requires
  a new version;
- update the contract registry/models first;
- regenerate `contracts/schemas/brain-api.v1.json`;
- run `--check`, the full test suite and compile checks;
- only then publish SDK artifacts from the checked-in schema.

## Remaining Phase 8 client work

Slice 5A provides the shared generation input. Slice 6 added the thin,
framework-free TypeScript client over the existing HTTP/WebSocket surface
(`clients/typescript/`, see `docs/typescript-client.md`): its runtime method
table and error codes are verified against this artifact, and its HTTP tests run
live against the real Core transport. Java packaging is still open. These
clients may live in Product-owned repositories while consuming this Core-owned
contract artifact.
