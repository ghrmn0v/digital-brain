# Digital Brain Product / Connectors

The local-first Product and Connector layer that integrates with Core Brain and
Fly. This repository does not implement Core Brain intelligence or Fly
behaviour; it provides stable API and event boundaries for both.

## Capabilities

- Local Tasks CRUD, with due dates, priority and recurring task series
- Local Calendar CRUD, with timezone, reminders and recurrence metadata
- LinkedIn job ingestion, normalization, deduplication, status history and reports
- `AUTOMATIC`, `ASK_FIRST` and `OFF` permission rules
- Action registry, approval/rejection audit and structured action responses
- Event and schedule automation engine; automation always passes through the
  permission engine
- Generic connector event ingestion and a real LinkedIn job adapter
- Durable SQLite event and delivery layer, with Core Brain delivery and a Fly
  SSE stream
- Connector status and health UI, with credential-free management
- Product Timeline, Settings, Dashboard and a responsive UI
- PC-only Developer Mode workspace, with a typed capability that defaults to off
- Shared, read-only Developer Information feed for PC and mobile
- Projection of Core Brain `developer.bug_detected` events, with an audit trail
  of proposal approval and rejection that never executes anything
- Fly developer event delivery through the existing normalized event layer,
  unchanged
- Runtime Zod validation, stable API errors and mutation idempotency
- Vitest unit and integration tests against a clean test SQLite database

## Tech stack

- Next.js 16 App Router, React 19, TypeScript
- Tailwind CSS 4, Lucide React
- Prisma 7 + SQLite + `better-sqlite3`
- Zod 4
- EventEmitter2
- Vitest 5
- npm

## Running locally

Requires Node.js `22.12+`.

```bash
cd digital-brain-product
npm ci
cp .env.example .env
npm run db:deploy
npm run db:seed
npm run dev
```

App: [http://localhost:3000](http://localhost:3000)

Health and readiness: [http://localhost:3000/api/health](http://localhost:3000/api/health)

Prisma Studio:

```bash
npm run db:studio
```

Background delivery and one-time schedule worker:

```bash
npm run worker
```

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Next.js development server |
| `npm run build` | Production build |
| `npm run worker` | Event delivery and schedule polling worker |
| `npm run lint` | ESLint |
| `npm run typecheck` | Next route type generation and TypeScript |
| `npm test` | Unit and integration tests |
| `npm run test:coverage` | Coverage report |
| `npm run test:smoke` | Real Next.js HTTP runtime smoke test with an isolated database |
| `npm run check` | Lint, typecheck and tests |
| `npm run verify` | Prisma validation, check and production build |
| `npm run db:migrate -- --name <name>` | Create a new development migration |
| `npm run db:deploy` | Apply the committed migrations |
| `npm run db:seed` | Seed default permissions, connectors and settings |
| `npm run db:studio` | Prisma Studio |

## Architecture

```text
External services
  -> Connector normalize/ingest
  -> IntegrationEvent + EventDelivery (SQLite)
  -> Core Brain HTTP delivery
  -> Fly SSE / HTTP delivery
  -> Event automations
  -> Permission engine
  -> Action registry
  -> Tasks / Calendar / Jobs
  -> Product UI
```

Server-only modules are grouped under `src/modules`:

- `tasks`, `calendar`, `jobs`: domain validation and persistence
- `permissions`: policy resolution
- `actions`: registry, approval and execution audit
- `automations`: event and schedule conditions, and action dispatch
- `connectors`: connector lifecycle and the LinkedIn normalizer
- `events`: normalized events, durable delivery and SSE
- `settings`, `timeline`: Product-owned data

API documentation: [`docs/API_CONTRACTS.md`](docs/API_CONTRACTS.md)

## Developer Mode and platform boundaries

- **Developer Mode:** PC only, default `OFF`. Repository context, proposal
  decisions and the Fly-related developer workspace appear only in the desktop
  layout.
- **Developer Information:** read-only developer data produced by Core Brain,
  surfaced on PC and mobile through the same API.
- The mobile client does not see the Developer Mode toggle, local repository
  analysis, Git/test/deploy actions, or the Fly UI.
- In the mobile app `developer-information` is a read-only feed.
- A `developer.bug_detected` event is validated against an exact Zod payload
  schema first; title and message are stored exactly as Core Brain sent them.
- Proposal approve/reject only changes the audit status. It does not start an
  `ActionExecution`, Git operation, test run or deployment.
- Repository, Git, testing and deployment capabilities exist only as ports.

## Default security behaviour

- Task and event creation from Core Brain is `ASK_FIRST`
- Task and event deletion, and job applications, are `OFF`
- An unknown action is `400 ACTION_NOT_SUPPORTED`
- An unknown permission is `ASK_FIRST`
- A disabled permission is `OFF`
- Automation cannot bypass the permission rules
- The LinkedIn connector does not create relevance or decisions
- `relevanceReason` is shown only as data sent by Core Brain
- Raw credentials are never stored in SQLite or shown in the UI

## External integrations

In `.env`:

```dotenv
SERVICE_API_TOKEN="strong-random-service-token"
CORE_BRAIN_URL="http://127.0.0.1:8765/v1/brain"
CORE_BRAIN_USER_ID="usr_local_owner"
CORE_BRAIN_API_TOKEN=""
FLY_EVENTS_URL="http://127.0.0.1:8080/api/v1/events"
FLY_API_TOKEN=""
```

`CORE_BRAIN_USER_ID` is required for Brain delivery: the Brain isolates every
event by user, and this local-first Product acts for a single owner. Without it
the delivery fails loudly rather than attributing the data to a wrong identity.

With an empty URL the event is still stored in SQLite and the delivery stays
`PENDING`. Once a URL is configured, the worker retries the `core_brain` and
`fly` consumers a bounded number of times.

The Brain's ingest contract distinguishes a handled request from a stored event:
it answers HTTP 200 with `outcome` in the body, where `accepted` and `duplicate`
mean the event is held and `rejected` means it is not. Delivery inspects that
outcome, so a rejected event is never recorded as delivered.

There is no LinkedIn scraping in this project. The LinkedIn endpoint only
accepts the normalized state forwarded by an authorized connector worker; real
OAuth and data acquisition are a separate concern for each supported provider
API.

## Boundaries with Core Brain and Fly

- The Product does not create Core Brain intelligence.
- The Product does not store People or Memory data in its local database.
- Fly receives only an event stream; Fly behaviour decisions belong to the Fly
  owner.
- Brain events are accepted at `/api/brain-events`.
- Fly events are read from the `/api/fly-events` SSE stream.
- Action intent and outcome are sent and accepted using the same contract from
  Core Brain.

## Verification

```bash
npm run verify
npm audit
```

`npm run verify` checks the Prisma schema, lint, TypeScript, the test suite and
the production build.
