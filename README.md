# Fly / Connectome subsystem

Real fruit fly brain inspired behavior engine. FlyWire adult mushroom body wiring
drives the behavior; the brain is data-driven so larger real connectome exports can be
loaded through the same pipeline.

## Layout

- `connectome/` — Python behavior engine (real brain, stdlib-only)
- `backend/`    — Spring Boot (incoming, Faza 1)
- `desktop/`    — Electron + Three.js (incoming, Faza 2)

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