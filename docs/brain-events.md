# Brain Events — Infrastructure (Phase 8, Slice 1)

Core Brain communicates outward exclusively through **typed Brain Events**. The
event infrastructure makes that communication **transport-independent**: Core
Brain never knows or cares how a consumer receives an event (HTTP, WebSocket,
Electron IPC, mobile push, message bus). Consumers attach a sink.

```
Brain state transition / reasoning result
        │
        ▼
 BrainEventEmitter  (pure builder, deterministic payloads)
        │
        ▼
 BrainEventDispatcher  ──▶  EventSink (port)  ──▶  Product / Fly / Mobile / …
```

## Components

| file | role |
|---|---|
| `contracts/brain_events/events.py` | the `BrainEvent` contract + `BrainEventType` enum (open, additive) |
| `core/brain_events/emitter.py` | `BrainEventEmitter` — deterministic builders of every event payload |
| `core/brain_events/sink.py` | `EventSink` port + `NullEventSink` (default) + `CollectingEventSink` (capture) |
| `core/brain_events/dispatch.py` | `BrainEventDispatcher` — emitter + sink wiring; `emit_plan(...)` |
| `core/brain_events/pipeline.py` | `DevModePipeline` — optional sink; developer.* events |
| `core/service/brain_service.py` | `BrainService` — emits events for real state transitions |

## Event catalogue

| event type | emitted when (real transition) | by |
|---|---|---|
| `developer.bug_detected` | a potential bug is found | pipeline |
| `developer.fix_proposed` | a fix is proposed (permission requested) | pipeline |
| `developer.test_result` | test results are supplied & interpreted | pipeline |
| `developer.review_finding` | a review finding is generated | pipeline |
| `developer.deploy_proposed` | a deploy is proposed (never executed) | pipeline |
| `memory.created` | a memory is durably created (e.g. via ingest) | service |
| `preference.updated` | a preference is written/superseded | service |
| `learning.signal.detected` | a feedback record is learned from | service |
| `decision.created` | a BrainDecision is produced | service |
| `action.proposed` | a pure-data action proposal is added to a decision | service |

Events are emitted **because a real state transition happened** — never merely
because an enum value exists. Undeclared enum members (`memory.updated`,
`person.created`, …) are reserved and not emitted until a corresponding real
Brain behaviour exists.

## Guarantees

- **Structured payloads** — validated `BrainEvent` (extra="forbid") with a
  documented, open payload dict.
- **Ownership** — every event carries `user_id`; sinks expose per-user views;
  no cross-user leakage (tested).
- **Correlation** — `correlation_id` propagates from the logical operation
  through every event it produces (tested end to end). It always lives in
  `payload["correlation_id"]` (key present; `None` when absent) — it is not
  duplicated in a second envelope.
- **Timestamps** — always timezone-aware UTC.
- **Deterministic** — same inputs → same event *content* (ids/timestamps are
  minted, never faked).
- **Idempotency** — a duplicate logical operation (e.g. re-ingesting an
  already-receipted event) emits no duplicate events.
- **No execution** — events describe proposals/transitions; nothing executes.

### Delivery contract (Phase 8, Slice 4B)

The full, testable semantics of delivering events to consumers is specified in
**[docs/event-delivery.md](event-delivery.md)**. Summary:

- **Identity** — `BrainEvent.id` is the stable, minted-once per-emission
  identity; the deduplication key for consumers.
- **Ordering** — within one synchronous operation, delivery order == emission
  order (single-threaded sequential `emit`). No global ordering, no sequence
  numbers.
- **Delivery mode** — in-process, synchronous, **at-most-once, best-effort**;
  no persistence, retry, replay or ack. **Not** a durable message queue.
- **Correlation** — grouped via `payload["correlation_id"]`, never rewritten.
- **User ownership** — consumers must filter by envelope `user_id`; tested at
  every layer.

`EventSink` is the consumer port itself. The completed WebSocket adapter is one
bounded `EventSink` implementation; future mobile clients or buses use the same
port without changing Core Brain.

## Using a sink

```python
from core import build_brain_service, CollectingEventSink

sink = CollectingEventSink()
service = build_brain_service(":memory:", sink=sink)

outcome = service.analyze_developer(developer_context, correlation_id="corr-1")
for event in sink.emitted:
    print(event.type.value, event.payload.get("correlation_id"))
```

A REST/Kafka/mobile adapter is another `EventSink` implementation and needs no
changes inside Core Brain. Durable/broker delivery remains outside Phase 8.