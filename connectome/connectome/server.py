import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from connectome.event_processor import normalize_event, normalize_feedback
from connectome.influence import ProductionInfluence
from connectome.loader import load_wiring
from connectome.model import Brain
from connectome.policy import PRIORITY_LEVEL, decide
from connectome.reward import map_feedback
from connectome.simulate import inject_event
from connectome.state_machine import states
from connectome.store import SqliteStore

DEFAULT_PORT = 8601
DEFAULT_DB = os.environ.get("FLY_DB", str(Path.home() / ".fly" / "connectome.db"))


class FlyBrainService:
    def __init__(
        self,
        steps: int = 40,
        store: Optional[SqliteStore] = None,
        influence: Optional[ProductionInfluence] = None,
        flight: bool = True,
    ):
        self.graph = load_wiring()
        self.brain = Brain(self.graph)
        self.store = store or SqliteStore()
        persisted = self.store.load_weights()
        if persisted:
            self.brain.weights.update(persisted)
        self.steps = steps
        self.influence = influence or ProductionInfluence()
        self.flight = flight
        self.lock = threading.RLock()

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "fly-python-behavior",
            "graph": self.graph.meta.get("name", "unknown"),
            "neurons": self.graph.meta.get("neurons", 0),
            "decisions": self.store.counts().get("decisions", 0),
            "feedback": self.store.counts().get("feedback", 0),
            "learned_influence": self.influence.summary(),
            "flight_mode": "on" if self.flight else "off",
        }

    def flight_mode(self) -> Dict[str, Any]:
        return {"flight": self.flight}

    def set_flight(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            self.flight = bool(raw.get("flight"))
            return {"flight": self.flight}

    def behavior(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            event = normalize_event(raw)
            inject_event(self.brain, event)
            for _ in range(self.steps):
                self.brain.step()
            decision = decide(self.brain, event, flight=self.flight)
            state, influence = self.influence.apply(event, decision["state"])
            result = {
                "event": event.name,
                "source": event.source,
                "priority": event.priority,
                "context": event.context,
                "fetch": state,
                "priority_level": decision["priority"],
                "confidence": decision["confidence"],
                "flight": self.flight,
                "activity": {gid: round(a, 4) for gid, a in self.brain.mbon_vector().items()},
                "influence": influence,
            }
            self.store.record_decision(result, behavior_id=event.id)
            return result

    def feedback(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            fb = normalize_feedback(raw)
            reward = map_feedback(fb.feedback)
            before = dict(self.brain.weights)
            self.brain.deliver_reward(reward.value)
            for _ in range(3):
                self.brain.step()
            delta = {
                f"{k[0]}->{k[1]}": round(self.brain.weights[k] - before[k], 5)
                for k in before
                if abs(self.brain.weights[k] - before[k]) > 1e-6
                and self.graph.nodes[k[0]].type == "kc"
            }
            self.store.record_feedback(fb.feedback, reward.value, behavior_id=fb.behavior_id)
            self.store.save_weights(self.brain.weights)
            return {
                "behavior_id": fb.behavior_id,
                "feedback": fb.feedback,
                "reward_value": reward.value,
                "synapse_delta": delta,
            }

    def reset(self) -> Dict[str, Any]:
        with self.lock:
            self.brain.reset()
            return {"status": "reset"}

    def states(self) -> Dict[str, Any]:
        return {
            "states": [
                {"name": name, "priority": spec["priority"], "priority_level": PRIORITY_LEVEL.get(name, "LOW"),
                 "animation": spec["animation"], "duration_ms": spec["duration_ms"]}
                for name, spec in states.items()
            ]
        }


class Handler(BaseHTTPRequestHandler):
    service: FlyBrainService = None
    routes = {
        "POST /behavior": lambda s, payload: s.behavior(payload),
        "POST /feedback": lambda s, payload: s.feedback(payload),
        "POST /reset": lambda s, payload: s.reset(),
        "POST /mode": lambda s, payload: s.set_flight(payload),
    }

    def _send_json(self, code: int, body: Dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, self.service.health())
        elif self.path == "/states":
            self._send_json(200, self.service.states())
        elif self.path == "/mode":
            self._send_json(200, self.service.flight_mode())
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        action = self.routes.get(f"POST {self.path}")
        if action is None:
            self._send_json(404, {"error": "not_found"})
            return
        payload = self._read_json()
        try:
            self._send_json(200, action(self.service, payload))
        except Exception as exc:
            self._send_json(500, {"error": "internal_error", "detail": str(exc)})

    def log_message(self, fmt, *args):
        pass


def make_server(
    port: int = DEFAULT_PORT,
    steps: int = 40,
    db_path: Optional[str] = None,
    influence: Optional[ProductionInfluence] = None,
    flight: bool = True,
) -> ThreadingHTTPServer:
    store = SqliteStore(db_path)
    handler = type(
        "FlyHandler",
        (Handler,),
        {"service": FlyBrainService(steps=steps, store=store, influence=influence, flight=flight)},
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fly behavior engine HTTP service")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--db", default=DEFAULT_DB, help="sqlite path for learning persistence")
    parser.add_argument(
        "--influence",
        choices=("off", "auto", "on"),
        default=None,
        help="Phase 7: allow the offline RL policy to influence production "
        "(default: env FLY_LEARNED_INFLUENCE or 'off'; auto requires the evaluate "
        "verdict CANDIDATE_FOR_PRODUCTION)",
    )
    parser.add_argument(
        "--flight",
        choices=("off", "on"),
        default=None,
        help="flight mode: 'on' lets joyful events turn into flights (TAKEOFF/FLYING/LANDING), "
        "'off' keeps the fly perched and only reacting (default: env FLY_FLIGHT_MODE or 'on')",
    )
    args = parser.parse_args()

    flight = (args.flight or os.environ.get("FLY_FLIGHT_MODE", "on")) == "on"

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    server = make_server(
        port=args.port,
        steps=args.steps,
        db_path=args.db,
        influence=ProductionInfluence(mode=args.influence),
        flight=flight,
    )
    print(
        f"fly-python-behavior listening on 127.0.0.1:{args.port} (db={args.db})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()