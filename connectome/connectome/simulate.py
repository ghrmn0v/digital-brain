import argparse
import hashlib
import json
import sys
from typing import Dict

from connectome.event_processor import Event, normalize_event, normalize_feedback
from connectome.loader import load_wiring
from connectome.model import Brain
from connectome.policy import decide
from connectome.reward import map_feedback
from connectome.state_machine import StateMachine

CTX_CHANNELS = 8


def _context_channels(*parts) -> int:
    seen = set()
    for part in parts:
        if part:
            seen.add(hashlib.sha256(str(part).encode()).digest()[0] % CTX_CHANNELS)
    return len(seen)


def inject_event(brain: Brain, event: Event) -> None:
    brain.clear_inputs()
    brain.set_input("PN", event.priority)
    ctx = event.context or {}
    covered = _context_channels(
        event.name, event.source, ctx.get("topic", ""), ctx.get("urgency", "")
    )
    context_drive = 0.15 + 0.6 * (covered / CTX_CHANNELS)
    brain.set_input("CTX", min(1.0, context_drive))


def run_brain(brain: Brain, event: Event, steps: int = 40) -> Dict:
    inject_event(brain, event)
    for _ in range(steps):
        brain.step()
    return decide(brain, event)


def run_simulation(raw_event: Dict, feedback: str = None, steps: int = 40) -> Dict:
    graph = load_wiring()
    brain = Brain(graph)
    machine = StateMachine()

    event = normalize_event(raw_event)
    decision = run_brain(brain, event, steps)
    machine.transition_to(decision["state"])

    result = {
        "event": event.name,
        "source": event.source,
        "priority": event.priority,
        "brain_state": decision,
        "fly_state": machine.current,
        "activity": {gid: round(act, 4) for gid, act in brain.mbon_vector().items()},
    }

    if feedback:
        fb = normalize_feedback({"event": "fly_feedback", "behavior_id": f"behavior_{event.id}", "feedback": feedback})
        reward = map_feedback(fb.feedback)
        before = dict(brain.weights)
        inject_event(brain, event)
        for _ in range(steps):
            brain.step()
        brain.deliver_reward(reward.value)
        for _ in range(3):
            brain.step()
        changed = {
            k: round(brain.weights[k], 4) for k in before if abs(brain.weights[k] - before[k]) > 1e-6 and graph.nodes[k[0]].type == "kc"
        }
        result["feedback"] = {
            "type": fb.feedback,
            "reward_value": reward.value,
            "synapse_delta": changed,
        }
    return result


def _parse_payload(value: str) -> Dict:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Fly brain on an event.")
    parser.add_argument("--event", default="important_message", help="event name")
    parser.add_argument("--priority", type=float, default=0.85, help="priority 0..1")
    parser.add_argument("--source", default="whatsapp", help="event source")
    parser.add_argument("--context", default=None, help='JSON context e.g. {"topic":"job"}')
    parser.add_argument("--feedback", default=None, help="feedback type to apply (e.g. dismissed)")
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    context = _parse_payload(args.context or "{}")
    raw = {
        "event": args.event,
        "source": args.source,
        "priority": args.priority,
        "context": context,
    }
    result = run_simulation(raw, feedback=args.feedback, steps=args.steps)
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        decision = result["brain_state"]
        print(f"event       : {result['event']} ({result['source']}, p={result['priority']})")
        print(f"fly state   : {result['fly_state']}  -> priority level {decision['priority']}")
        print(f"confidence  : {decision['confidence']}")
        print(f"mbon        : {result['activity']}")
        if result.get("feedback"):
            print(f"feedback    : {result['feedback']['type']} (reward={result['feedback']['reward_value']})")
            print(f"synapses    : {result['feedback']['synapse_delta']}")


if __name__ == "__main__":
    main()