# Fly / Connectome subsystem

Real fruit fly brain inspired behavior engine. FlyWire adult mushroom body wiring
drives the behavior; the brain is data-driven so larger real connectome exports can be
loaded through the same pipeline.

## Layout

- `connectome/`       — Python behavior engine (real brain, stdlib-only, learns)
- `backend/`          — Spring Boot service boundary (events, WhatsApp webhook, WS)
- `desktop/`          — Electron + Three.js (incoming, Faza 2)
- `whatsapp-gateway/` — WhatsApp → Spring Boot gateway (isolated from rendering)
- `doc/`              — spec (`job need to be done.pdf`)

## Connectome internals

- `connectome/connectome/`        — engine: wiring, rate-model brain, states, policy, server (stdlib-only)
- `connectome/connectome/store.py` — SQLite persistence (decisions/feedback/weights, survives restart)
- `connectome/connectome/reference/` — flywire_live_service (real FlyWire caveclient prototype)
- `connectome/connectome/training/analysis.py` — offline metrics (reward_rate, policy_agreement, distribution)
- `connectome/connectome/training/dataset.py` — labeled training set from the live store (CSV + JSONL)
- `connectome/connectome/training/evaluation.py` — Faza 6: learned policy vs real baseline (reward + verdict)
- `connectome/connectome/training/rl/` — Faza 5 offline RL experiment (torch-optional, isolated from inference)

## Learning roadmap (per spec)

Rule-based baseline (Faza 1) → structured data collection (2) → reward signals (3) →
offline experiments (4) → offline RL experiment (5) → **evaluate vs baseline (6, here)** →
gradual production influence (7). Production inference never uses an untested model.

## Run

### Python behavior engine

```
cd connectome
python3 -m unittest discover -s tests
python3 -m connectome.server --port 8601
```

CLI demo:

```
python3 -m connectome.simulate --event important_message --priority 0.9 --source whatsapp --context '{"topic":"job","urgency":"high"}'
python3 -m connectome.simulate --event important_message --priority 0.9 --feedback marked_useful
python3 -m connectome.simulate --event important_message --priority 0.9 --json
```

### Spring Boot service boundary

```
cd backend
mvn test
mvn spring-boot:run
```

Endpoints:

- `POST /api/v1/events`   — Brain event in, Fly behavior decision out (broadcast over WS)
- `POST /api/v1/feedback` — user feedback → reward signal
- `GET  /api/v1/health`   — service + python health
- `GET  /api/v1/states`   — fly state machine from python
- `GET  /api/v1/events/contract` — documented event contract
- `WS   /ws/fly`          — live behavior stream for Electron/Three.js
- `POST /api/v1/whatsapp/webhook` — WhatsApp gateway ingestion (normalized to event)
- `GET  /api/v1/whatsapp/webhook` — probe/status

### WhatsApp → Fly pipeline

```
WhatsApp → whatsapp-gateway (Node/whatsapp-web.js)
        → Spring Boot /api/v1/whatsapp/webhook (normalization: type→event+priority)
        → Python behavior engine (connectome brain decides)
        → WebSocket broadcast → Electron/Three.js Fly (behavior + speech bubble)
```

The gateway never talks to the renderer; Spring Boot normalizes every message into
the internal event contract (`source=whatsapp`). Message body is truncated to 80
chars and only the preview is forwarded to the UI.

Run the gateway:

```
cd whatsapp-gateway
npm install
FLY_BACKEND_URL=http://localhost:8080/api/v1/whatsapp/webhook node server.js   # scan the QR once
```

WhatsApp session (`whatsapp-gateway/.wwebjs_auth/`) is intentionally git-ignored
(credentials are never committed).

### Offline RL experiment (Faza 5)

Requires torch in an isolated interpreter (system python is stdlib-only):

```
cd connectome
python3 -m unittest discover -s tests                     # 50 tests (no torch needed)
python3 -m connectome.training.rl.offline_exp --episodes 400   # with torch installed
```

The experiment warms up the RL network offline and reports policy agreement against
the deterministic baseline on the WhatsApp message-type cases. Outputs land in
`connectome/connectome/training/rl/experiments/` (git-ignored: reproducible artifacts).

### Evaluate learned policy vs baseline (Faza 6)

```
cd connectome
python3 -m connectome.training.evaluation
```

Runs the real rule-based baseline (connectome brain) and the trained RL policy
(Faza 5 snapshot) on the same scenarios, scoring each reaction through the
REWARD_MAP-based user-feedback model, then emits a Phase 7 readiness verdict:

```
policy agreement vs baseline: 40%
mean reward delta:            +0.0000
verdict:                      COLLECT_MORE_DATA
safe to influence production: False
```

The phase-7 gate is deliberate: production absorbs the learned policy only when it
matches the baseline reaction (or strictly improves reward) on every scenario.

### Electron + Three.js visual layer

```
cd desktop
npm install
node --test test/
npm start
```

When the backend stack is down, the app falls back to a local demo cycle so the
fly keeps moving. Feedback buttons drive real learning through the backend.

`desktop/models/` holds the low-poly fly asset (OBJ + texture) from the reference
prototype, ready for an optional visual upgrade. 
### Collect a labeled training dataset

```
cd connectome
python3 -m connectome.training.dataset --db /tmp/opencode/fly_test.db
```

Exports every recorded decision joined to its user feedback (via `behavior_id`, which is kept
canonical end-to-end: `behaviorId == event.id` from the Spring boundary through the WS message
into the feedback loop) as CSV + JSONL in `connectome/connectome/training/datasets/` (git-ignored),
with dataset statistics (labeled/unlabeled, reward balance).
