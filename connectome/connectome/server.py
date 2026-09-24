import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from connectome.event_processor import normalize_event, normalize_feedback
from connectome.loader import load_wiring
from connectome.model import Brain
from connectome.policy import PRIORITY_LEVEL, decide
from connectome.reward import map_feedback
from connectome.simulate import inject_event
from connectome.state_machine import states

DEFAULT_PORT = 8601


class FlyBrainService:
    def __init__(self, steps: int = 40):
        self.graph = load_wiring()
        self.brain = Brain(self.graph)
        self.steps = steps
        self.lock = threading.RLock()

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "fly-python-behavior",
            "graph": self.graph.meta.get("name", "unknown"),
            "neurons": self.graph.meta.get("neurons", 0),
        }

    def behavior(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            event = normalize_event(raw)
            inject_event(self.brain, event)
            for _ in range(self.steps):
                self.brain.step()
            decision = decide(self.brain, event)
            return {
                "event": event.name,
                "source": event.source,
                "priority": event.priority,
                "context": event.context,
                "fetch": decision["state"],
                "priority_level": decision["priority"],
                "confidence": decision["confidence"],
                "activity": {gid: round(a, 4) for gid, a in self.brain.mbon_vector().items()},
            }

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


def make_server(port: int = DEFAULT_PORT, steps: int = 40) -> ThreadingHTTPServer:
    handler = type(
        "FlyHandler",
        (Handler,),
        {"service": FlyBrainService(steps=steps)},
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fly behavior engine HTTP service")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--steps", type=int, default=40)
    args = parser.parse_args()

    server = make_server(port=args.port, steps=args.steps)
    print(f"fly-python-behavior listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()