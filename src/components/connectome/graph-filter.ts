import type {
  ConnectomeEdgeDto,
  ConnectomeNodeDto,
} from "@/modules/connectome";

/**
 * Source filtering for the graph.
 *
 * An event does not store its source on the node, so the relationship is read
 * back off the `emitted` edges: the source node is literally the parent of the
 * events it produced. Filtering therefore keeps the chosen source, the events it
 * emitted, and the one hop of structure hanging off those events — a thread, a
 * consumer, a proposal — so selecting a source never leaves a thread node
 * pointing at events that are no longer drawn.
 */

export interface SourceSelection {
  nodes: ConnectomeNodeDto[];
  edges: ConnectomeEdgeDto[];
}

export function filterBySource(
  nodes: ConnectomeNodeDto[],
  edges: ConnectomeEdgeDto[],
  source: string | null,
): SourceSelection {
  if (!source) return { nodes, edges };

  const sourceNodeId = `source:${source}`;
  const byId = new Map(nodes.map((node) => [node.id, node]));
  if (!byId.has(sourceNodeId)) return { nodes: [], edges: [] };

  const events = new Set<string>();
  for (const edge of edges) {
    if (edge.kind === "emitted" && edge.source === sourceNodeId) {
      events.add(edge.target);
    }
  }

  // One hop out from the kept events, so their threads and consumers survive.
  const keep = new Set<string>([sourceNodeId, ...events]);
  for (const edge of edges) {
    if (events.has(edge.source)) keep.add(edge.target);
    if (events.has(edge.target)) keep.add(edge.source);
  }

  return {
    nodes: nodes.filter((node) => keep.has(node.id)),
    edges: edges.filter(
      (edge) => keep.has(edge.source) && keep.has(edge.target),
    ),
  };
}
