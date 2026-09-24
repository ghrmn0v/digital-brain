# Ingestion Pipeline (Phase 2)

Deterministic, dependency-light ingest: validated source events from
connectors become memories — with deduplication, receipts and full
traceability. No LLM, no brokers, no new dependencies beyond
Python + Pydantic + SQLite.

## Pipeline

```
RAW EVENT
 → 1. schema validation   (Pydantic NormalizedSourceEvent contract)
 → 2. business validation (JSON-serializable payload; handler fields present)
 → 3. dedup check         (idempotency_key else event id, scoped per user)
 → 4. processing          (event type → memory candidates, deterministic)
 → 5. memory creation     (MemoryService)
 → 6. receipt persistence (only the LAST write marks success)
 └──────── one outcome: ACCEPTED | DUPLICATE | REJECTED | PROCESSING_FAILED
```

## Public API

```python
from core import build_ingestion

service = build_ingestion("data/brain.sqlite3")   # one shared SQLite file
result = service.ingest(raw_event)                 # Mapping[str, Any]
service.close()
```

`result` is an `IngestionResult`:

| outcome            | meaning                                            | memory written? | receipt written? |
|--------------------|----------------------------------------------------|-----------------|------------------|
| `REJECTED`         | failed schema/business validation                  | no              | no               |
| `DUPLICATE`        | same logical event already accepted                | no              | no               |
| `ACCEPTED`         | valid and processed                                | maybe           | yes              |
| `PROCESSING_FAILED`| valid but could not be processed/persisted         | no              | no               |

`ACCEPTED` with `memory_ids=()` means the event was valid but this pipeline
maps no memory for its type — it is still receipted so it is not re-processed.

## Validation split (two stages, kept separate)

- **Schema** — `core/ingestion/validation.py: parse_source_event`. Shape, types,
  required fields, `extra="forbid"`, the `source.<provider>.<action>` type
  pattern. Broken frames are rejected, never repaired.
- **Business** — `validate_business`. First the payload must be JSON-serializable
  (so it can be hashed/receipted); then, for event types the pipeline maps, the
  fields the handler needs must actually be present.

## Deduplication

`core/ingestion/deduplication.py` derives an `EventIdentity` from every event:

- `idempotency_key` when provided (producer-guaranteed retries), else `event id`;
- composite key `"<provider>:<value>"`, scoped by `user_id` — two users may
  reuse the same idempotency key without colliding.

Receipts persist in a dedicated `ingestion_receipts` table (PK
`identity_kind, identity_key, user_id`) that survives restarts. `payload_hash`
(canonical JSON sha256) is stored for audit, not used to decide duplicates.

## Processing: event types → memories

`DeterministicEventProcessor` holds a registry of `(provider, action)` →
mapping rule. An event `source.<provider>.<rest>` is looked up by
`(provider, "<rest>")`. Unknown types are ACCEPTED with no memory — a mapping
can be added later without re-running old events.

Built-in rules today (all conservative, no interpretation — only the verified
structured fields become memory content):

| event type                        | memory type  | payload field(s) required |
|-----------------------------------|--------------|---------------------------|
| `source.linkedin.profile_updated` | FACT         | —                         |
| `source.linkedin.job_seen`        | FACT         | `company`                 |
| `source.calendar.event_created`   | EVENT        | `summary`                 |
| `source.whatsapp.message_received`| INTERACTION  | `text`                    |
| `source.todo.task_created`        | EPISODE      | `description`             |

## Traceability

Every memory produced by ingestion carries provenance back to exactly one
event:

- `source` = the event's `Source` (`provider`/`component`/`version`);
- `related_events` = `[event.id]`;
- `valid_from` = `event.occurred_at`;
- `metadata`: `source_event_id`, `source_event_timestamp`, `occurred_at`,
  `provider`, `event_type`, and `correlation_id` when present.

## Failure behavior (A–E)

- **A invalid** → `REJECTED`, nothing stored, no receipt → a corrected retry works.
- **B duplicate** → `DUPLICATE` (points at `duplicate_of_event_id`), no second memory.
- **C valid unsupported** → `ACCEPTED`, no memory.
- **D valid supported** → `ACCEPTED`, processor runs, memories are written.
- **E memory-creation failure** → `PROCESSING_FAILED`; the transaction rolls
  back so the receipt is dropped and a later retry re-attempts the whole event.

## Atomicity (and its documented limit)

`build_ingestion` creates ONE SQLite connection (autocommit mode) shared by
the receipt store and the memory store, both with `auto_commit=False`, and
drives both inside one `BEGIN IMMEDIATE … commit/rollback` transaction. Order:
process → create memories → record receipt (last). If anything fails, the
whole unit rolls back — a receipt can never exist without its memories.

Standalone wiring (repos with their own connections + `NullTransaction` in
`transaction.py`) is supported for tests and simple embeddings; there the two
stores commit independently — not atomic together, documented as a limitation.

## Repository layout

```
core/ingestion/
  exceptions.py              IngestionError hierarchy
  models.py                  IngestionOutcome / IngestionResult / IngestionReceipt
  validation.py              schema + business validation
  deduplication.py           EventIdentity / identity_of / payload_hash
  handlers.py                MappingRule registry + content builders (one truth)
  processor.py               EventProcessor port + DeterministicEventProcessor
  receipt_repository.py      EventReceiptRepository port
  sqlite_receipt_repository.py  ingestion_receipts table
  service.py                 IngestionService (small public API)
  transaction.py             NullTransaction / SqliteTransaction
  factory.py                 build_ingestion wiring
tests/test_ingestion.py      validation, dedup, mappings, isolation, failure,
                             persistence, atomicity, traceability
```

Added in Phase 2 on top of the Phase 1 Memory Engine; the Phase 0 contract
`NormalizedSourceEvent.type` pattern was relaxed to also accept `_` in
segments (`profile_updated`, `message_received`, …) — fully backwards
compatible with existing names.