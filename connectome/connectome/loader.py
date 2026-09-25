import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_WIRING = "data/adult_mb_wiring.json"


def default_wiring_path() -> Path:
    return Path(__file__).parent / DEFAULT_WIRING


@dataclass
class Edge:
    source: str
    target: str
    synapses: float
    plastic: bool
    physiology: str
    weight: float = 1.0

    @property
    def key(self) -> Tuple[str, str]:
        return (self.source, self.target)


@dataclass
class NodeGroup:
    id: str
    population: int
    type: str


@dataclass
class WiringGraph:
    meta: Dict
    nodes: Dict[str, NodeGroup] = field(default_factory=dict)
    edges: Dict[Tuple[str, str], Edge] = field(default_factory=dict)

    def group(self, gid: str) -> NodeGroup:
        return self.nodes[gid]

    def incoming(self, gid: str) -> List[Edge]:
        return [e for e in self.edges.values() if e.target == gid]

    def outgoing(self, gid: str) -> List[Edge]:
        return [e for e in self.edges.values() if e.source == gid]

    def plasticity_edges(self) -> List[Edge]:
        return [e for e in self.edges.values() if e.plastic]

    def total_incoming_synapses(self, gid: str) -> float:
        return sum(e.synapses for e in self.incoming(gid))

    def validate(self) -> None:
        for gid, group in self.nodes.items():
            if group.population <= 0:
                raise ValueError(f"group {gid!r} has non-positive population")
        for edge in self.edges.values():
            if edge.source not in self.nodes:
                raise ValueError(f"edge source {edge.source!r} not in nodes")
            if edge.target not in self.nodes:
                raise ValueError(f"edge target {edge.target!r} not in nodes")
            if edge.synapses <= 0:
                raise ValueError(f"edge {edge.key} has non-positive synapse count")


def load_wiring(path=None) -> WiringGraph:
    source = Path(path) if path else default_wiring_path()
    data = json.loads(source.read_text(encoding="utf-8"))

    graph = WiringGraph(meta=data.get("meta", {}))
    for node in data["nodes"]:
        graph.nodes[node["id"]] = NodeGroup(
            id=node["id"],
            population=int(node["population"]),
            type=node["type"],
        )
    for edge in data.get("edges", []):
        e = Edge(
            source=edge["from"],
            target=edge["to"],
            synapses=float(edge["synapses"]),
            plastic=bool(edge.get("plastic", False)),
            physiology=edge.get("physiology", "excitatory"),
            weight=float(edge.get("weight", 1.0)),
        )
        graph.edges[e.key] = e
    graph.validate()
    return graph