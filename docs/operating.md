# Operating the Core Brain directly

The Brain is a backend, not a widget. This is how to run it, talk to it, and
see what it actually did — without any Product UI in the loop.

## Run it

```bash
# HTTP (the usual choice). Loopback only by default.
python -m core.transport.http --host 127.0.0.1 --port 8765 --db data/brain.sqlite3

# Pick the LLM provider (see "Providers" below).
python -m core.transport.http --port 8765 --provider gemini

# WebSocket: one connection bound to one user.
python -m core.transport.websocket --port 8766

# stdio: one JSON request per stdin line.
python -m core.transport.stdio --db data/brain.sqlite3
```

Liveness:

```bash
curl -s http://127.0.0.1:8765/health
```

## Configuration

Every variable the Brain reads, and nothing else. All are optional: with none of
them set the Brain runs fully on its deterministic provider. See
[`.env.example`](../.env.example) for a copyable template, which is committed;
a filled-in `.env` is gitignored and must stay that way.

| Variable | Default | Meaning |
|---|---|---|
| `BRAIN_LLM_PROVIDER` | `heuristic` | Provider name. `gemini` to call Gemini. Same as `--provider`, which wins. |
| `BRAIN_LOG_ENABLED` | off | Emit structured records to stderr. |
| `BRAIN_LOG_LEVEL` | `info` | `debug` / `info` / `warning` / `error`. |
| `BRAIN_LOG_FORMAT` | `json` | `json` (one object per line) or `text`. |
| `GEMINI_ENABLED` | off | Explicit opt-in for the Gemini provider. |
| `GEMINI_API_KEY` | — | Credential. Never logged; never returned. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model id. |
| `GEMINI_API_BASE` | Google endpoint | Override for a proxy. |
| `GEMINI_TIMEOUT_SECONDS` | `30` | Per-request timeout. |
| `GEMINI_TEMPERATURE` | `0.2` | Sampling temperature. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Response cap. |

Bind address, port and database path are **flags, not environment variables**,
so a deployed Brain always states where it listens.

`GEMINI_ENABLED` is separate from the key on purpose: a stray credential in the
environment cannot silently start sending data to a third party.

## Providers

`heuristic` is deterministic, offline and always available. `gemini` calls
Google and **falls back to `heuristic` on any failure** — timeout, provider
error, or output that fails structured validation. The Brain never fails a
request because a model was unavailable.

A provider is an *inference* step. It never writes memory, preferences or
identity: those are the Brain's, and the only path to them is the ingestion and
learning pipelines. The model receives bounded context the Brain chose to send.

## The API in one loop

19 methods, all `POST /v1/brain` with one `ApiRequest` in and one
`ApiResponse` out. `describe` returns the live registry and every schema.

```bash
call() { curl -s -X POST http://127.0.0.1:8765/v1/brain \
  -H 'content-type: application/json' -d "$1"; }

# 1. ingest
call '{"id":"r1","method":"ingest","version":"v1","params":{"event":{
  "id":"evt-1","type":"source.calendar.event_created",
  "timestamp":"2026-09-26T09:00:00Z","occurred_at":"2026-09-26T09:00:00Z",
  "user_id":"usr_demo","source":{"provider":"calendar"},
  "payload":{"summary":"Hackathon planning meeting"},
  "correlation_id":"corr-1"}}}'

# 2. retrieve it again
call '{"id":"r2","method":"search","version":"v1","params":{
  "user_id":"usr_demo","text":"hackathon","limit":5}}'

# 3. ask a question in plain language
call '{"id":"r3","method":"chat","version":"v1","params":{
  "user_id":"usr_demo","message":"what do I know about the hackathon?"}}'
```

### `search` — retrieval

The read path the Brain was missing. Returns **this user's own** memories,
ranked, each with `score`, `matched_fields`, `ranking_reason`, provenance and
`correlation_id`. `user_id` is required and cannot be widened.

An empty query lists by importance and recency instead of returning nothing.

### `chat` — one grounded turn

Retrieves memories, preferences, people and learned evidence, answers from
them, and reports **which memories it used** in `grounded_in`. Two guarantees
are load-bearing:

* the answer is **grounded or honestly empty** — if the Brain has nothing, it
  says so rather than inventing;
* a model answer is **never stored**. Learning is recorded only when you pass
  `target_event_id`, because the Brain never invents a traceability id.

`provider` and `fallback_used` are always present, so you can always tell a model
answer from a deterministic one.

### Inspecting the rest of the Brain

There is no separate debug endpoint: the same user-scoped reads you would use
in an application are the ones you should use to inspect the Brain.

| Question | Method |
|---|---|
| What do you know about X? | `search` |
| What happened with this person? | `people_timeline` |
| Who do I know? | `people_summary` |
| What do I prefer? | `preferences`, `developer_preferences` |
| What have I learned? | `learning_status`, `feedback_history` |
| How would you help me? | `personalization_profile` |
| What can you do? | `describe` |

## Observability

Off by default — a library must not write to a host's stderr uninvited.

```bash
BRAIN_LOG_ENABLED=1 BRAIN_LOG_LEVEL=info python -m core.transport.http --port 8765
```

Records answer the questions you actually have while debugging: what arrived,
which user it belongs to, the `correlation_id`, whether memory was created,
whether learning happened, whether an action was proposed, and whether a provider
or the fallback answered.

```json
{"event":"event.received","event_id":"evt-1","event_type":"source.calendar.event_created","correlation_id":"corr-1","level":"info","logger":"digital_brain.service","ts":"..."}
{"event":"ingest.accepted","event_id":"evt-1","user_id":"usr_demo","memory_count":1,"correlation_id":"corr-1","level":"info","logger":"digital_brain.service","ts":"..."}
{"event":"search.completed","user_id":"usr_demo","returned":2,"has_query":true,"level":"info","logger":"digital_brain.service","ts":"..."}
{"event":"ingest.rejected","event_id":"evt-2","reason":"event 'source.calendar.event_created' requires a non-empty string payload field 'summary'","level":"warning","logger":"digital_brain.service","ts":"..."}
```

Two rules the logger enforces rather than trusting call sites:

* **no secrets.** Secret-shaped keys are replaced with `***`, and the Gemini key
  is registered as non-emittable the moment it is read, so it cannot escape
  through a provider error message either.
* **no private history.** Records carry identifiers, counts, decisions and
  reasons. Memory content, payloads and queries are never emitted, so a log
  stream cannot become a second copy of someone's private data.

## Error semantics

Six canonical codes, each mapped to exactly one HTTP status.

| Code | HTTP | Meaning |
|---|---|---|
| `bad_request` | 400 | Malformed envelope. |
| `unknown_method` | 404 | No such method. |
| `version_unsupported` | 400 | Not `v1`. |
| `validation_error` | 422 | Params or payload failed their typed model. |
| `not_configured` | 503 | A dependency is not wired. |
| `internal_error` | 500 | Unexpected failure. |

**A request that was handled correctly is `ok: true` even when the *event* was
rejected.** `ingest` reports `outcome: "accepted" | "duplicate" | "rejected"`
with a `reason` in the result, at HTTP 200. That is deliberate: the call
succeeded, and the event's fate is data, not a transport failure. A consumer
that needs to act on a rejection must read `outcome` — treating HTTP 200 alone
as "the event was stored" is a bug, and this is the one place it is easy to get
wrong. Rejections are logged at `warning` so they are visible either way.

## Security posture

Deliberate prototype decisions, unchanged:

* **No authentication.** Any caller that can reach the port may act as any
  `user_id`. The HTTP and stdio transports bind loopback by default for this
  reason; the WebSocket transport additionally refuses a non-loopback bind
  unless `--allow-unauthenticated-non-loopback` is passed.
* **User isolation is enforced inside the Brain**, not by the caller: every
  read and write is scoped by `user_id` in SQL, so a caller cannot widen it.

Both are worth revisiting before any non-local deployment.
