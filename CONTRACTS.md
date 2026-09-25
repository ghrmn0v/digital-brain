# Digital Brain — Contracts (Phase 0)

Canonical, versioned data contracts that let the three ownership areas build
independently without renegotiating each other's interfaces.

## 1. Who owns the contracts

Repo `ghrmn0v/digital-brain`, branch `brain`, package `contracts/` — owned by
**CORE BRAIN (Hüseyn)**. Changes to the package shape, the envelope, or any
versioned field MUST go through this repo. Both other teams import/compile
against these schemas (Python directly; TS/Java from the exported JSON Schema
via `model.model_json_schema()`).

## 2. Boundaries

| Area | Owner | Role against these contracts |
|---|---|---|
| Core Brain | Hüseyn | **Sole writer** of memory, people, decisions, feedback, brain events. Consumer of `NormalizedSourceEvent`. |
| Product / Connectors | Ayxan | **Producer** of normalized source events (LinkedIn, Calendar, Tasks, Jobs, user UI actions). **Executor** of `ProposedAction` after permission, never the Brain. |
| Connectome / Fly | Fly | Producer of normalized source events (WhatsApp pipeline). Producer of RL `Feedback` (`kind=reward`, `source=fly`). Consumer of brain events/state for behavior. |

System flow:

```
EXTERNAL WORLD
   ↓
NormalizedSourceEvent(s)          ← produced by Ayxan / Fly
   ↓
CORE BRAIN  (memory · context · people · reasoning · proposals)
   ↓
BrainEvent(s) + BrainDecision/ProposedAction(s)
   ↓
PRODUCT executes (after permission)  ·  FLY reacts
```

## 3. Core Brain boundary

- Brain owns: memory lifecycle, people/relationships, semantic search, context,
  reasoning, intent, action *proposals*, preferences, importance, feedback
  understanding, personalization, brain events, decision log.
- Brain NEVER executes external actions. See **Action execution rule**.
- Brain does not own: auth/session UX, permission enforcement, connector clients,
  realtime UI, action execution infrastructure.

## 4. Product / Connector boundary (Ayxan)

- Connectors normalize external world activity into `NormalizedSourceEvent`
  (see `contracts/events/source_event.py`). Payload stays open — no Brain
  dependency on a specific connector.
- Product consumes `ProposedAction` after a Brain decision and returns
  execution **outcome** as `Feedback` (`source=product`, `kind=outcome`).
- Permission: Product interprets `requested_permission_level`; the Brain
  requests, Product grants/denies.

## 5. Fly boundary (Connectome)

- Fly produces WhatsApp-derived `NormalizedSourceEvent`s and RL training
  signals as `Feedback` (`source=fly`, `kind=reward`).
- Fly consumes `BrainEvent`s / brain state for Fly behavior and reactions.
- Only `kind == reward` feedback feeds reward signals. Everything else is
  contextual, not reward.

## 6. Contracts

| Contract | Module | Purpose |
|---|---|---|
| `EventEnvelope` | `contracts/common/envelope.py` | Outer shape of every event: `id,type,version,timestamp,user_id,source,payload` |
| `NormalizedSourceEvent` | `contracts/events/` | Canonical event entering the Brain; connector-independent |
| `Memory` | `contracts/memory/` | Brain-owned memory with confidence, importance, temporal validity, supersession |
| `Person` + `ExternalIdentity` | `contracts/people/` | Unified person; external IDs kept separate for future identity resolution |
| `BrainDecision` / `ProposedAction` | `contracts/decisions/` | Brain proposes; Product executes |
| `Feedback` | `contracts/feedback/` | Labeled signals: source (user/product/fly/system) × kind (explicit/implicit/outcome/reward) |
| `BrainEvent` / `BrainEventType` | `contracts/brain_events/` | Typed events the Brain emits to consumers |
| API registry / schema bundle | `contracts/api/registry.py`, `contracts/schemas/brain-api.v1.json` | Canonical v1 method/model mapping and offline TS/Java generator input |

Every model is `extra="forbid"` (typos rejected), serializable via
`model_dump_json()`, and round-trips through
`Model.model_validate_json(...)`.

## 7. NormalizedSourceEvent

- `type` is dot-separated and always starts with `source.`, e.g.
  `source.linkedin.connection.accepted`, `source.whatsapp.message.received`,
  `source.calendar.event.created`.
- `timestamp` = when recorded/ingested; `occurred_at` = when it happened in the
  world.
- `correlation_id` ties related events; `idempotency_key` allows safe re-delivery.
- `subject` is the person the event concerns (if known), `payload` is open.

## 8. BrainDecision / ProposedAction — action execution rule

```
Brain proposes  →  BrainDecision { proposed_actions: [ProposedAction] }
                       ↓
Product checks permission (requested_permission_level)  →  executes  →  result
```

- `ProposedAction` is **pure data**: intent + parameters + reason + requested
  permission level. It has no execution fields or behavior.
- Core Brain must never call external APIs, send messages, or write to
  external systems directly. All external effects happen in Product.
- Execution success/failure returns as `Feedback` (`source=product`,
  `kind=outcome`) so the Brain can learn from results.

## 9. Feedback — not everything is a reward

Distinguish by two explicit labels:

- `source` (where): `user` · `product` · `fly` · `system`
- `kind` (what): `explicit` · `implicit` · `outcome` · `reward`

Only `kind == reward` (typically `source == fly`/`system`) feeds RL reward
signals. `user + explicit` feeds preference/importance learning. The Brain
decides how to use a signal from these two labels.

## 10. Brain Events

Fixed, predictable event names (`contracts/brain_events/`):

`memory.created` · `memory.updated` · `person.created` · `person.updated` ·
`preference.updated` · `action.proposed` · `decision.created` ·
`learning.signal.detected`

Payload shapes are documented on `BrainEventType`; adding a new member is an
additive (backward-compatible) change.

## 11. API schema distribution

`contracts/api/registry.py` is the public method-to-model source of truth.
`BrainApi.describe()` and the deterministic offline bundle
`contracts/schemas/brain-api.v1.json` are generated from that same registry.
The packaged artifact contains request/response/error/event/stream-frame
contracts, ordered method entries and local JSON Schema references for external
TypeScript/Java clients. The additive `people_timeline` method returns
`PeopleTimelineResult` with bounded historical entries, durability and
provenance. The artifact is data-free and must be regenerated with
`python -m contracts.api.schema` whenever the v1 API contract changes. A build
should run `python -m contracts.api.schema --check` to reject stale artifacts.
See `docs/schema-distribution.md`.

## 12. Versioning rules

Every externally exchanged contract carries `version: "v1"`.

- **Additive change** (new optional field, new enum member, new event type,
  wider payload) → backward compatible, same version.
- **Breaking change** (removed/renamed field, changed type, changed required
  set, changed semantics) → bump the version in `ContractVersion`
  (e.g. `"v2"`) and keep backwards consumers working if possible.
- Consumers must pass through the `version` field unchanged and fail loudly on
  versions they do not understand.

## 13. Validation

Tests live in `tests/test_contracts.py` (stdlib `unittest`, no infra):

```
python -m unittest discover -s tests -t .
```

Covered: required fields, unknown fields rejected, invalid versions rejected,
confidence/importance bounds, naive→UTC normalization, temporal
historical-vs-current memory, feedback target requirement, brain-event enum,
`ProposedAction` has no execution surface, JSON round-trip serialization.