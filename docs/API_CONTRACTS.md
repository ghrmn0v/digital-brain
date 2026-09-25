# Product / Connectors API Contracts

Contract version: `1.0`

Base URL: `http://localhost:3000`

## Authentication

Browser requests are accepted from the local same-origin application. Internal or remote service requests must use:

```http
Authorization: Bearer <SERVICE_API_TOKEN>
```

Cross-origin browser requests are rejected. Raw connector credentials are never returned by Product APIs.

## Response format

Success:

```json
{
  "data": {},
  "meta": {
    "requestId": "uuid"
  }
}
```

Paginated success:

```json
{
  "data": [],
  "meta": {
    "requestId": "uuid",
    "pagination": {
      "page": 1,
      "limit": 25,
      "total": 0,
      "totalPages": 0
    }
  }
}
```

Error:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "requestId": "uuid",
    "details": {}
  }
}
```

Mutations that create resources accept an optional `Idempotency-Key` header. Reusing a key with the same payload replays the stored result; reusing it with another payload returns `409`.

## Tasks

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/tasks` | List and filter tasks |
| `POST` | `/api/tasks` | Create a task |
| `GET` | `/api/tasks/:id` | Read a task |
| `PATCH` | `/api/tasks/:id` | Update or complete a task |
| `DELETE` | `/api/tasks/:id` | Delete a task |

Supported query parameters: `q`, `status`, `priority`, `page`, `limit`.

Wire statuses: `todo`, `in_progress`, `blocked`, `done`, `cancelled`.

## Calendar

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/calendar` | List events in a date range |
| `POST` | `/api/calendar` | Create an event |
| `GET` | `/api/calendar/:id` | Read an event |
| `PATCH` | `/api/calendar/:id` | Update an event |
| `DELETE` | `/api/calendar/:id` | Delete an event |

Supported query parameters: `q`, `status`, `from`, `to`, `page`, `limit`.

`endsAt` must be later than `startsAt`. `timeZone`, when supplied, must be an IANA time zone. Recurrence currently supports `FREQ=DAILY|WEEKLY|MONTHLY|YEARLY` with an optional `INTERVAL`.

## Jobs

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/jobs` | List/filter jobs |
| `POST` | `/api/jobs` | Idempotently upsert a job by source and external ID |
| `GET` | `/api/jobs/:id` | Read a job |
| `PATCH` | `/api/jobs/:id` | Update status or Core Brain-supplied context |
| `DELETE` | `/api/jobs/:id` | Archive a job while retaining history |
| `GET` | `/api/jobs/report` | Produce a period report without inventing relevance reasons |

Job statuses: `seen`, `saved`, `ignored`, `applied`, `archived`.

`relevanceReason` is displayed only when supplied by Core Brain or another authorized upstream service. The LinkedIn connector never creates a relevance explanation.

## Actions and permissions

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/actions` | Request an action from Core Brain or automation |
| `GET` | `/api/actions` | List action executions |
| `GET` | `/api/actions/:id` | Read an execution |
| `POST` | `/api/actions/:id/approve` | Approve a pending action |
| `POST` | `/api/actions/:id/reject` | Reject a pending action |
| `GET/POST` | `/api/permissions` | List/upsert policies |
| `PATCH/DELETE` | `/api/permissions/:id` | Update/remove a policy |

Action request:

```json
{
  "source": "core_brain",
  "action": "tasks.create_task",
  "payload": {
    "title": "Send CV",
    "dueAt": "2026-09-30T12:00:00.000Z"
  },
  "correlationId": "brain-request-123"
}
```

Action response:

```json
{
  "actionId": "uuid",
  "success": true,
  "status": "completed",
  "result": {}
}
```

Permission levels:

- `AUTOMATIC`: execute immediately.
- `ASK_FIRST`: persist as `pending_approval` and wait for a user decision.
- `OFF`: persist a rejected audit record and do not execute.

Unknown actions and unknown permission policies fail closed. Missing policy defaults to `ASK_FIRST`.

## Automations

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET/POST` | `/api/automations` | List/create rules |
| `GET/PATCH/DELETE` | `/api/automations/:id` | Read/update/delete a rule |
| `POST` | `/api/automations/:id/run` | Manually trigger a rule |
| `POST` | `/api/internal/automations/schedules` | Process due one-time schedules |

Event conditions use a restricted JSON DSL with explicit paths and operators. Automation actions always pass through `/api/actions`; rules cannot bypass permissions.

## Connectors and events

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/connectors` | List safe connector status |
| `PATCH` | `/api/connectors/:id` | Enable/disable a connector |
| `POST` | `/api/internal/connectors/:id/health` | Record worker health |
| `POST` | `/api/connectors/events/ingest` | Persist a normalized generic connector event |
| `POST` | `/api/connectors/linkedin/jobs/ingest` | Validate, upsert and publish LinkedIn jobs |
| `POST` | `/api/brain-events` | Persist a Core Brain `BrainEvent` (legacy Product event shape still accepted) |
| `GET` | `/api/fly-events` | Fly/Connectome SSE stream with durable backlog replay |
| `POST` | `/api/internal/event-deliveries` | Retry pending external deliveries |

Normalized event (Product's internal storage shape):

```json
{
  "id": "stable-event-id",
  "source": "linkedin",
  "type": "job.discovered",
  "timestamp": "2026-09-24T12:00:00.000Z",
  "payload": {
    "jobId": "job-id"
  },
  "metadata": {
    "schemaVersion": "1.0",
    "connectorVersion": "1.0.0"
  }
}
```

This shape is **not** the Core Brain wire contract. On the wire Product speaks
the Brain contract in both directions:

- **Product -> Brain** (`CORE_BRAIN_URL`, default `http://127.0.0.1:8765/v1/brain`):
  one `ApiRequest` envelope, `method: "ingest"`, with a Brain
  `NormalizedSourceEvent` in `params.event` — canonical `source.<provider>.<action>`
  type, `occurred_at`, a `source` object and `CORE_BRAIN_USER_ID` as `user_id`.
  Product's `metadata.correlationId` is sent as the Brain's `correlation_id`;
  Product's `metadata` is not forwarded, because the Brain rejects unknown fields.
- **Brain -> Product** (`POST /api/brain-events`): a canonical Core Brain
  `BrainEvent` (`id`, `type`, `timestamp`, `user_id`, `source`, `payload`,
  `version`, `related_ids`). Product maps it into its internal shape; the legacy
  Product shape is still accepted for compatibility.

Integration events and per-consumer deliveries are persisted in SQLite. Delivery retries are bounded; the local worker calls the retry endpoint periodically through `npm run worker`.

## Developer Mode və Developer Information

Developer Mode bir PC capability-dir; Developer Information isə hər iki platformda oxuna bilən Core Brain məlumatıdır.

| Method | Endpoint | Platform | Purpose |
| --- | --- | --- | --- |
| `GET/PUT` | `/api/developer-mode` | Desktop only | Read or change the default-off capability |
| `GET` | `/api/developer-information` | Desktop + mobile | Read shared Core Brain developer information |
| `GET` | `/api/developer-proposals` | Desktop only | Read actionable bug proposals while mode is enabled |
| `POST` | `/api/developer-proposals/:id/approve` | Desktop only | Record proposal approval only |
| `POST` | `/api/developer-proposals/:id/reject` | Desktop only | Record proposal rejection only |

Desktop requests use the presentation capability header:

```http
X-Product-Client-Platform: desktop
```

This header separates product presentation; it is not an intelligence or authorization boundary.

The accepted event namespace mirrors the Core Brain catalogue exactly:

- `developer.bug_detected`
- `developer.fix_proposed`
- `developer.test_result`
- `developer.review_finding`
- `developer.deploy_proposed`

`developer.explanation` is intentionally absent: Core keeps an explanation inside
the payload of the event it belongs to instead of emitting a second event. The
deployment event is `developer.deploy_proposed`, because Core proposes the
deployment and Product decides whether to run it.

Only `developer.bug_detected` has a detailed Product projection in the current foundation. Its payload is:

```json
{
  "repository": "digital-brain",
  "file": "src/auth/login.ts",
  "line": 42,
  "column": 10,
  "title": "Possible null reference",
  "message": "user may be undefined before accessing user.email",
  "severity": "warning",
  "context": {}
}
```

`title` and `message` are opaque Core Brain output. Product validates and displays them without summarizing, rewriting, or generating replacements.

Approval and rejection update only `DeveloperProposal.status` and audit fields. They never call `actionService`, a Git adapter, a test runner, a deployment adapter, or Fly.

## Timeline and settings

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/timeline` | Product-owned chronological view |
| `GET/PUT` | `/api/settings` | List/upsert non-secret settings |
| `DELETE` | `/api/settings/:key` | Remove a setting |
| `GET` | `/api/health` | Database and schema readiness |

Memory and People data are not stored or interpreted by Product. Their UI and API adapter must use the contract agreed with the Core Brain engineer.
