# Product / Connectors Architecture

The repository now contains the local Product runtime and integration boundaries described below.

```text
External source
  -> validated connector ingestion
  -> normalized event
  -> SQLite IntegrationEvent + EventDelivery
     -> Core Brain HTTP adapter
     -> Fly SSE / HTTP adapter
  -> event automations
  -> Permission Engine
  -> Action Registry
  -> Task / Calendar / Job services
  -> Product UI
```

## Ownership boundaries

- Product owns external acquisition adapters, normalized events, local tasks/calendar/jobs, permissions, approval, automation dispatch, action execution, and product UI.
- Core Brain owns memory, people intelligence, reasoning, learning, relevance, and semantic retrieval.
- Fly owns Connectome behavior, rendering, and reaction logic. Product only publishes events.
- Product never derives job relevance or memory importance. It displays upstream explanations only when supplied.

## Platform capability model

```text
Core Brain developer events
          |
          v
Shared Product Developer Information API
          |
          +-- PC: optional Developer Mode workspace, proposal decisions, Fly
          |
          +-- Mobile: read-only Developer Information, no Fly/local analysis
```

Developer Mode is stored as a default-off boolean capability and exposed only through desktop presentation. Shared Developer Information is platform-independent Product data. Neither client contains repository analysis or other AI logic.

## Reliability decisions

- Runtime validation uses Zod at every external/API boundary.
- Local writes use Prisma transactions where multi-record state must stay consistent.
- Create mutations and machine actions support idempotency.
- Action policy defaults to `ASK_FIRST`; destructive actions default to `OFF`.
- Integrations use durable event and per-consumer delivery records.
- Delivery retries are bounded and executed by a separate local worker.
- SSE replays recent durable events and then follows the process-local event bus.
- Tests use an isolated SQLite database and never modify `dev.db`.

See [`API_CONTRACTS.md`](product/API_CONTRACTS.md) for external request and response contracts.
