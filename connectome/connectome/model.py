import math
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
        self.dan_gate = 0.0
        self.dan_sign = 0

    def reset(self) -> None:
        self.activity = {gid: 0.0 for gid in self.graph.nodes}
        self.inputs = {gid: 0.0 for gid in self.graph.nodes}
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
            total += edge.synapses * weight * self.activity[edge.source]
        scale = self.graph.total_incoming_synapses(gid) or 1.0
        drive = self.inputs[gid] + total / scale
        return max(0.0, min(1.0, drive + self.config["noise"]))

    def step(self) -> None:
        dt = self.config["dt"]
        tau = self.config["tau"]
        targets = {gid: _activity_fn(gid, self._drive(gid), self.config) for gid in self.graph.nodes}
        for gid, target in targets.items():
            current = self.activity[gid]
            self.activity[gid] = current + (dt / tau) * (target - current)
        self._update_plasticity()

    def _update_plasticity(self) -> None:
        cfg = self.config
        gate = self.dan_gate
        if gate <= 1e-9:
            return
        for edge in self.graph.plasticity_edges():
            kc_act = self.activity.get(edge.source, 0.0)
            mbon_act = self.activity.get(edge.target, 0.0)
            key = edge.key
            delta = cfg["eta"] * gate * kc_act
            if self.dan_sign >= 0:
                delta *= (1.0 - mbon_act)
            else:
                delta = -cfg["eta"] * gate * kc_act
            updated = self.weights[key] + delta
            updated -= cfg["decay"] * (self.weights[key] - 1.0)
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