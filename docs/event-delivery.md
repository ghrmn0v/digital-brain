# Event Delivery Contract (Phase 8 Slice 4B)

Transport-independent semantics for delivering Brain events to consumers. This
is a **stability contract, not new machinery**: it makes the existing
`EventSink` pipeline explicit and testable so that real-time transports
(WebSocket, mobile push, message bus) can be added later without silently
changing behavior.

**This is NOT a durable message queue.** There is no Redis, Kafka, persistent
event store, retry worker, ack protocol or delivery ledger. Delivery is
in-process, synchronous and best-effort.

---

## 1. The consumer port

`core/brain_events/sink.py` defines the single consumer boundary:

```python
@runtime_checkable
class EventSink(Protocol):
    def emit(self, event: BrainEvent) -> None: ...
```

A consumer is **any object with `emit(event)`** — nothing else. The Brain
(`BrainService`) and the Developer pipeline call `emit` for every state
transition they produce; the consumer decides whether and how to process the
event. The port knows nothing about HTTP, WebSocket, mobile, databases,
Redis, Kafka or cloud infrastructure, and the event infrastructure must never
import them (architecture guard test).

```
 BrainService / DevModePipeline
        │ emit(event) ─► EventSink (consumer)  ─►  Product / Fly / Mobile / …
```

Future transports (WebSocket/mobile/bus) are implemented as `EventSink`
implementations over the same `emit` call; Core Brain needs no changes.

## 2. Event identity

Every emitted `BrainEvent` carries a stable identity in the envelope field
`id` (`evt_…`, minted from a UUID at emission time).

- **Minted once, never reused**: one emission produces exactly one `id`.
- **Deliveries of the same emission share the `id`**: redelivering the same
  event object (rebroadcast, packet retry, buffer redelivery) keeps the `id`
  unchanged, so a consumer can recognise a duplicate.
- **Distinct emissions always have distinct `id`s**: re-running the same
  logical operation produces a *new* event with a *new* `id`, even when
  content is identical. Content equality is never a proxy for identity.
- Consequences:
  - deduplication key = `event.id`;
  - replay/counting must key on `event.id`, not on payload hashing.

Do not invent a second event-id. (`payload["event_id"]` on some developer
events is the *domain* id — e.g. a `finding_id` — not the delivery identity.)

## 3. Ordering

- **Guaranteed**: events emitted during one synchronous BrainService
  operation are delivered to a sink **in emission order**. All `emit` calls
  happen sequentially on one thread inside a single call stack (e.g.
  `analyze_developer`: developer.bug_detected/fix_proposed/test_result/
  review_finding/deploy_proposed, then decision.created, then one
  action.proposed per proposal; `record_feedback`:
  learning.signal.detected before any preference.updated).
- **Not guaranteed**: global ordering across operations, processes,
  transports or sink instances. There is **no sequence number** on events;
  timestamps may tie (both minted at the same instant), so consumers may not
  derive order from timestamps — only the delivery stream order is
  meaningful, and only within one operation.
- Transport frames (e.g. the stdio daemon) preserve that order on one
  stream: events emitted while a request runs are written before its response
  and in emission order. That is a per-operation, per-stream guarantee, not a
  global one.

## 4. Delivery semantics

The current system is **at-most-once, best-effort, in-process**.

- Each emission is handed to a sink exactly once **or not at all**.
- There is no persistence: a sink without storage (e.g. `NullEventSink`),
  a dead stream or a crashed producer simply loses the event.
- There is no retry, no replay, no acknowledgement, no outbox. If
  `emit()` raises, the failure propagates toward the caller
  (surfaced at a transport boundary as a typed error) and the event is not
  redelivered.
- Logical-operation idempotency is separate from delivery: re-ingesting an
  already-receipted source event produces **no new transition** and therefore
  **no duplicate events** — but that is the Brain's idempotency, not a
  delivery guarantee.

## 5. Duplicate handling

Consumer rule: **identify duplicates by `event.id`**.

```python
seen: set[str] = set()
def on_event(event):
    if event.id in seen:
        return  # duplicate delivery — skip
    seen.add(event.id)
    process(event)
```

No distributed deduplication infrastructure is provided (or needed) at this
stage. Two deliveries of the same emission are the *same object identity*
(`id`), so a per-consumer `id` set is a sufficient duplicate filter for
at-most-once delivery.

## 6. Correlation semantics

- `correlation_id` lives in `payload["correlation_id"]` on **every** emitted
  event type. It is always present as a key and is `None` when no correlation
  was supplied.
- One logical operation propagates the same `correlation_id` through **all**
  events it produces (ingest, record_feedback, analyze_developer). Events on
  a transport frame do **not** carry the request `id` — correlate a stream of
  events back to a request/operation through `correlation_id`.
- Consumers group events into correlation chains via
  `event.payload.get("correlation_id")`; it must never be rewritten.

## 7. User ownership

- `user_id` is a stable envelope field on every `BrainEvent` and is never
  forged: transitions are emitted for the user that owns the operation.
- Consumers **must** filter by `event.user_id`; a consumer that ignores
  ownership will silently mix users. (`CollectingEventSink.by_user` exists
  for exactly this.)
- User isolation is tested continuously: events of one user must never be
  attributable to another, from emitter, sink, service and transport
  (stdio/HTTP) layers. No authorization framework is added here — ownership is
  made explicit and testable, not enforced by a platform.

## 8. What is NOT guaranteed

- Global ordering across operations/processes/transports (no sequence numbers).
- Exactly-once or at-least-once delivery (retry/replay/ack do not exist).
- Durability or retention (no persistent event store).
- Ordering derivable from `timestamp` (timestamps may tie).
- Delivery to a consumer that is not attached as a sink at emission time
  (no buffering, no replay of past events).
- Authentication/authorization of consumers (no auth infrastructure).

## 9. Guidance for future WebSocket/mobile consumers

1. Implement `EventSink.emit(event)` and the request-side adapter
   (`BrainApi.handle`) only; never touch core modules.
2. Assume at-most-once, best-effort delivery: add the transport's own
   durability exactly where the product needs it, outside Core Brain.
3. Deduplicate inbound events by `event.id`.
4. Filter every event by `event.user_id` before acting.
5. Group/stream events by `payload["correlation_id"]`.
6. Prefer per-operation ordering on a single connection; never claim global
   ordering.
7. Keep `id`, `type`, `version`, `timestamp`, `user_id` and
   `payload["correlation_id"]` untouched on the wire.