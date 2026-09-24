# Fly / Connectome subsystem

Real fruit fly brain inspired behavior engine. FlyWire adult mushroom body wiring
drives the behavior; the brain is data-driven so larger real connectome exports can be
loaded through the same pipeline.

## Layout

- `connectome/`       — Python behavior engine (real brain, stdlib-only, learns)
- `backend/`          — Spring Boot service boundary (events, WhatsApp webhook, WS)
- `desktop/`          — Electron + Three.js (incoming, Faza 2)
- `whatsapp-gateway/` — WhatsApp → Spring Boot gateway (isolated from rendering)

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

### Electron + Three.js visual layer

```
cd desktop
npm install
node --test test/
npm start
```

When the backend stack is down, the app falls back to a local demo cycle so the
fly keeps moving. Feedback buttons drive real learning through the backend. 