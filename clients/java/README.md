# Digital Brain — Java Client (Phase 8, Slice 8)

A thin, dependency-free Java client for the Digital Brain API v1. Same contract
as the TypeScript client, same two transports, no Brain logic.

```java
import dev.digitalbrain.client.BrainClient;
import dev.digitalbrain.client.Json;

var http = BrainClient.http("http://127.0.0.1:8765", "usr_ali");
var params = Json.object();
params.put("person_id", "per_ali_1a2b3c4d");
var timeline = (Map<String, Object>) http.call("people_timeline", params);

var events = BrainClient.websocket("ws://127.0.0.1:8766", "usr_ali");
events.onEvent(event -> System.out.println(event.get("type")));
events.connect().join();
```

## What is here

| File | Purpose |
|---|---|
| `Json.java` | minimal strict JSON reader/writer (no third-party dependency) |
| `BrainApiException.java` | typed failure carrying the canonical `ApiError.code` |
| `BrainRequests.java` | request envelope, `ApiResponse` invariants, event rules |
| `BrainHttpClient.java` | `POST /v1/brain`, `GET /health` via `java.net.http` |
| `BrainWebSocketClient.java` | `/v1/brain?user_id=…` with response correlation + events |
| `BrainClient.java` | entry point (`http`, `websocket`, `knownMethods`) |
| `SelfCheck.java` | dependency-free self check with a `main` method |

Only the JDK is used: `java.net.http.HttpClient`, `java.net.http.WebSocket`,
`java.net.URI`, `java.util`. No Maven dependencies are declared in `pom.xml`.

## Behaviour mirrored from the TypeScript client

- `request(method, params)` returns the full `ApiResponse`; `call(...)` returns
  the typed result and throws `BrainApiException` for `ok=false`.
- Branch on `error.code`, never on an HTTP status.
- The configured `userId` is injected into params that carry `user_id`.
- WebSocket requests are correlated by request id; one response per request.
- Events are delivered at-most-once, deduplicated by `BrainEvent.id`, filtered
  by the connection identity, in arrival order; `correlationId(event)` groups
  related events. **No retry, no replay, no persistence.**
- `userId` is routing/isolation metadata, not authentication.

## Build and verify

```bash
cd clients/java
mvn -q package                                   # needs a JDK + Maven
java -cp target/classes dev.digitalbrain.client.SelfCheck
```

`SelfCheck` runs local checks (JSON round trip, escaping, event dedupe and user
filtering, correlation ids, the 17-method table, identity injection). Given a
`baseUrl` and a `userId` it also performs a live round trip against a running
Core:

```bash
python -m core.transport.http --port 8765 --db :memory:     # in the repo
java -cp target/classes dev.digitalbrain.client.SelfCheck http://127.0.0.1:8765 usr_ali
```

### Verification status — read this

**This client has NOT been compiled or executed in the repository's
environment.** That machine has a JRE only (`java` runtime present, `javac`
absent, the `jdk.compiler` module not in the boot layer) and installing a JDK or
Maven is out of scope for this project, so:

- no `mvn package`, `javac` or `java` run has been executed against these
  sources;
- no automated test has run against this code;
- the only mechanically verified property is a **static consistency test**
  (`tests/test_java_client_parity.py`) that compares the method table, the
  endpoint paths and the error codes in these sources against the canonical
  contract artifact. That test proves the client *names* the same methods the
  Core publishes; it does not prove the Java compiles or behaves.

A developer with a JDK should run `mvn -q package` and `SelfCheck` before using
this client. Treat it as a reviewed first draft, not a verified artifact.

## Out of scope

Durable delivery, retries, acknowledgements, auth sessions, notifications and
any rendering. The Brain proposes actions; Product executes them.
