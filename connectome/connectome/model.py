import math
import random
from typing import Dict, Optional

from connectome.loader import Edge, NodeGroup, WiringGraph

DEFAULT_CONFIG = {
    "dt": 0.5,
    "tau": 4.0,
    "kc_theta": 0.35,
    "eta": 0.004,
    "weight_max": 4.0,
    "weight_min": 0.05,
    "decay": 0.0005,
    "noise": 0.0005,
    "trace_decay": 0.85,
    "seed": None,
}


def _activity_fn(gid: str, drive: float, config: Dict) -> float:
    if gid.startswith("KC"):
        theta = config["kc_theta"]
        if drive <= theta:
            return 0.0
        return 1.0 - math.exp(-(drive - theta))
    if gid.startswith("DAN"):
        return max(0.0, min(1.0, drive))
    if gid.startswith("PN") or gid == "CTX":
        return max(0.0, min(1.0, drive))
    return math.tanh(max(0.0, drive))


class Brain:
    def __init__(self, graph: WiringGraph, config: Optional[Dict] = None):
        self.graph = graph
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.activity: Dict[str, float] = {gid: 0.0 for gid in graph.nodes}
        self.inputs: Dict[str, float] = {gid: 0.0 for gid in graph.nodes}
        self.weights: Dict[tuple, float] = {
            edge.key: edge.weight for edge in graph.edges.values()
        }
        self.initial_weights: Dict[tuple, float] = dict(self.weights)
        self.eligibility: Dict[tuple, float] = {
            edge.key: 0.0 for edge in graph.edges.values() if edge.plastic
        }
        self.dan_gate = 0.0
        self.dan_sign = 0
        seed = self.config.get("seed")
        self._rng = random.Random(seed)

    def reset(self) -> None:
        self.activity = {gid: 0.0 for gid in self.graph.nodes}
        self.inputs = {gid: 0.0 for gid in self.graph.nodes}
        self.eligibility = {key: 0.0 for key in self.eligibility}
        self.dan_gate = 0.0
        self.dan_sign = 0

    def set_input(self, gid: str, value: float) -> None:
        self.inputs[gid] = max(0.0, min(1.0, value))

    def clear_inputs(self) -> None:
        self.inputs = {gid: 0.0 for gid in self.graph.nodes}

    def _drive(self, gid: str) -> float:
        total = 0.0
        for edge in self.graph.incoming(gid):
            weight = self.weights[edge.key]
            sign = -1.0 if edge.physiology == "inhibitory" else 1.0
            total += sign * edge.synapses * weight * self.activity[edge.source]
        scale = self.graph.total_incoming_synapses(gid) or 1.0
        drive = self.inputs[gid] + total / scale
        drive += self._rng.gauss(0.0, self.config["noise"])
        return max(0.0, min(1.0, drive))

    def step(self) -> None:
        dt = self.config["dt"]
        tau = self.config["tau"]
        targets = {gid: _activity_fn(gid, self._drive(gid), self.config) for gid in self.graph.nodes}
        for gid, target in targets.items():
            current = self.activity[gid]
            self.activity[gid] = current + (dt / tau) * (target - current)
        self._update_traces()
        self._update_plasticity()

    def _update_traces(self) -> None:
        """Eligibility trace: KC activation persists for a few steps after the stimulus.

        Real associative memory in Drosophila needs the conditioned stimulus to still be
        available when dopamine arrives, so plasticity reads this decayed trace instead of
        the instantaneous KC activity.
        """
        decay = self.config["trace_decay"]
        keep = 1.0 - decay
        for edge in self.graph.plasticity_edges():
            key = edge.key
            self.eligibility[key] = (
                decay * self.eligibility.get(key, 0.0)
                + keep * self.activity.get(edge.source, 0.0)
            )

    def _update_plasticity(self) -> None:
        cfg = self.config
        gate = self.dan_gate
        if gate <= 1e-9:
            return
        for edge in self.graph.plasticity_edges():
            key = edge.key
            kc = self.eligibility.get(key, 0.0)
            mbon_act = self.activity.get(edge.target, 0.0)
            delta = cfg["eta"] * gate * kc
            if self.dan_sign >= 0:
                delta *= (1.0 - mbon_act)
            else:
                delta = -cfg["eta"] * gate * kc
            updated = self.weights[key] + delta
            prior = self.initial_weights.get(key, 1.0)
            updated -= cfg["decay"] * (self.weights[key] - prior)
            self.weights[key] = max(cfg["weight_min"], min(cfg["weight_max"], updated))
        self.dan_gate = 0.0
        self.dan_sign = 0

    def deliver_reward(self, value: float) -> None:
        value = max(-1.0, min(1.0, value))
        self.dan_gate = abs(value)
        self.dan_sign = 1 if value >= 0 else -1
        gate_act = abs(value)
        if value >= 0:
            self.set_input("DAN_PAM", gate_act)
            self.set_input("DAN_PPL", 0.0)
        else:
            self.set_input("DAN_PPL", gate_act)
            self.set_input("DAN_PAM", 0.0)

    def mbon_vector(self) -> Dict[str, float]:
        result = {}
        for gid, group in self.graph.nodes.items():
            if group.type == "mbon":
                result[gid] = self.activity[gid]
        return result

    def synapse_weight(self, source: str, target: str) -> float:
        return self.weights[(source, target)]