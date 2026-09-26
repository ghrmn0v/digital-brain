import { describe, expect, it } from "vitest";
import type { ConnectomeEdgeDto, ConnectomeNodeDto } from "@/modules/connectome";
import { filterBySource } from "@/components/connectome/graph-filter";

/**
 * Filtering a graph has an easy way to go wrong: keep the source's events but
 * drop the threads and consumers hanging off them, leaving nodes whose edges
 * point at things that are no longer drawn. These tests pin that it does not.
 */

function node(id: string, kind: ConnectomeNodeDto["kind"]): ConnectomeNodeDto {
  return {
    id,
    kind,
    label: id,
    detail: null,
    occurredAt: null,
    weight: 0.5,
    signals: [],
    href: null,
  };
}

function edge(
  source: string,
  target: string,
  kind: ConnectomeEdgeDto["kind"] = "emitted",
): ConnectomeEdgeDto {
  return { id: `${kind}:${source}->${target}`, source, target, kind, status: null };
}

const nodes: ConnectomeNodeDto[] = [
  node("source:whatsapp", "source"),
  node("source:calendar", "source"),
  node("event:a", "event"),
  node("event:b", "event"),
  node("thread:t1", "thread"),
  node("consumer:core_brain", "consumer"),
];

const edges: ConnectomeEdgeDto[] = [
  edge("source:whatsapp", "event:a"),
  edge("source:calendar", "event:b"),
  edge("event:a", "thread:t1", "threaded"),
  edge("event:a", "consumer:core_brain", "delivered"),
  edge("event:b", "consumer:core_brain", "delivered"),
];

describe("connectome source filter", () => {
  it("returns the whole graph when no source is chosen", () => {
    const result = filterBySource(nodes, edges, null);
    expect(result.nodes).toHaveLength(nodes.length);
    expect(result.edges).toHaveLength(edges.length);
  });

  it("keeps the chosen source and only the events it emitted", () => {
    const result = filterBySource(nodes, edges, "whatsapp");
    expect(result.nodes.map((n) => n.id)).toContain("source:whatsapp");
    expect(result.nodes.map((n) => n.id)).toContain("event:a");
    expect(result.nodes.map((n) => n.id)).not.toContain("event:b");
    expect(result.nodes.map((n) => n.id)).not.toContain("source:calendar");
  });

  it("keeps the structure hanging off the kept events", () => {
    const result = filterBySource(nodes, edges, "whatsapp");
    const ids = result.nodes.map((n) => n.id);
    // The thread and the consumer are reachable from event:a, so dropping them
    // would leave event:a with no meaning.
    expect(ids).toContain("thread:t1");
    expect(ids).toContain("consumer:core_brain");
  });

  it("never emits an edge whose endpoints are both present but unconnected", () => {
    const result = filterBySource(nodes, edges, "whatsapp");
    const ids = new Set(result.nodes.map((n) => n.id));
    for (const candidate of result.edges) {
      expect(ids.has(candidate.source)).toBe(true);
      expect(ids.has(candidate.target)).toBe(true);
    }
    // The calendar event is gone, so the edge that reached the consumer from it
    // must be gone too.
    expect(result.edges.some((e) => e.source === "event:b")).toBe(false);
  });

  it("shows nothing at all for a source that does not exist", () => {
    const result = filterBySource(nodes, edges, "linkedin");
    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
  });
});
