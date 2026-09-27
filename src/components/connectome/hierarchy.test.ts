import { describe, expect, it } from "vitest";
import type { ConnectomeEdgeDto, ConnectomeNodeDto } from "@/modules/connectome";
import { ROOT_ID, buildHierarchy, sourceOf } from "@/components/connectome/hierarchy";

/**
 * The map is a summary before it is a picture, so the invariant that matters is
 * that summarising loses nothing: every real node must appear exactly once, hang
 * off exactly one hub, and keep the edges that already existed between real
 * nodes. A hierarchy that quietly drops records is worse than a flat graph.
 */

function node(
  id: string,
  source: string,
  kind: ConnectomeNodeDto["kind"] = "event",
): ConnectomeNodeDto {
  return {
    id,
    kind,
    label: id,
    detail: null,
    occurredAt: null,
    weight: 0.5,
    signals: source ? [{ label: "Source", value: source }] : [],
    href: null,
  };
}

function edge(source: string, target: string): ConnectomeEdgeDto {
  return { id: `${source}->${target}`, source, target, kind: "emitted", status: null };
}

describe("connectome hierarchy", () => {
  it("puts a single Main Brain root above everything", () => {
    const { nodes } = buildHierarchy([node("a", "whatsapp")], []);
    const roots = nodes.filter((n) => n.kind === "source");
    expect(roots).toHaveLength(1);
    expect(roots[0].id).toBe(ROOT_ID);
    expect(roots[0].label).toBe("Main Brain");
  });

  it("routes real sources into the category their source belongs to", () => {
    const { nodes, hubOf } = buildHierarchy(
      [
        node("job-1", "linkedin"),
        node("msg-1", "whatsapp"),
        node("evt-1", "calendar"),
        node("brain-1", "core_brain"),
      ],
      [],
    );
    const hubLabel = (id: string) => nodes.find((n) => n.id === id)?.label;
    expect(hubLabel(hubOf.get("job-1")!)).toBe("People & Contacts");
    expect(hubLabel(hubOf.get("msg-1")!)).toBe("Conversations & Meetings");
    expect(hubLabel(hubOf.get("evt-1")!)).toBe("Conversations & Meetings");
    expect(hubLabel(hubOf.get("brain-1")!)).toBe("Tasks & Proposals");
  });

  it("keeps every input node exactly once, and never loses an unknown source", () => {
    const input = [
      node("a", "linkedin"),
      node("b", "whatsapp"),
      node("c", "core_brain"),
      node("d", "some-system-nobody-predicted"),
    ];
    const { nodes, hubOf } = buildHierarchy(input, []);
    for (const original of input) {
      const matches = nodes.filter((n) => n.id === original.id);
      expect(matches, original.id).toHaveLength(1);
      // A node with no recognised source still has to hang somewhere.
      expect(hubOf.get(original.id), original.id).toBeTruthy();
    }
  });

  it("omits a category with no members rather than showing it empty", () => {
    const { nodes } = buildHierarchy([node("a", "linkedin")], []);
    expect(nodes.some((n) => n.label === "Conversations & Meetings")).toBe(false);
    expect(nodes.some((n) => n.label === "Tasks & Proposals")).toBe(false);
  });

  it("connects the root to each hub and each hub to its members", () => {
    const { edges, hubOf } = buildHierarchy(
      [node("a", "linkedin"), node("b", "whatsapp")],
      [],
    );
    const hubIds = [...new Set(hubOf.values())];
    for (const hub of hubIds) {
      expect(
        edges.some((e) => e.source === ROOT_ID && e.target === hub),
        `root -> ${hub}`,
      ).toBe(true);
    }
    expect(edges.filter((e) => e.source === ROOT_ID)).toHaveLength(hubIds.length);
  });

  it("keeps the original edges between real nodes and drops synthetic duplicates", () => {
    const { edges } = buildHierarchy(
      [node("a", "whatsapp"), node("b", "whatsapp")],
      [edge("a", "b")],
    );
    expect(edges.some((e) => e.source === "a" && e.target === "b")).toBe(true);
    // No edge may point at a synthetic node twice.
    const spokeTargets = edges
      .filter((e) => e.source.startsWith("hub:"))
      .map((e) => e.target);
    expect(new Set(spokeTargets).size).toBe(spokeTargets.length);
  });

  it("is empty in, empty out", () => {
    const { nodes, edges, hubOf } = buildHierarchy([], []);
    expect(nodes).toHaveLength(0);
    expect(edges).toHaveLength(0);
    expect(hubOf.size).toBe(0);
  });

  it("reads the source from the provenance signal, not a guessed field", () => {
    expect(sourceOf(node("x", "linkedin"))).toBe("linkedin");
    expect(sourceOf(node("y", ""))).toBe("");
  });
});
