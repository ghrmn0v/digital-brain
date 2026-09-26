import { describe, expect, it } from "vitest";
import type { ConnectomeEdgeDto, ConnectomeNodeDto } from "@/modules/connectome";
import {
  boundsOf,
  createSimulation,
  neighboursOf,
  normaliseToFrame,
  radiusFor,
} from "@/components/connectome/force";

/**
 * The layout runs on the client, so these properties are what stop the graph
 * from feeling like noise: it must place the same data in the same place every
 * time, keep nodes on screen, and treat one selected node's neighbourhood as the
 * thing worth highlighting.
 */

function node(id: string, weight = 0.5): ConnectomeNodeDto {
  return {
    id,
    kind: "event",
    label: id,
    detail: null,
    occurredAt: null,
    weight,
    signals: [],
    href: null,
  };
}

function edge(source: string, target: string): ConnectomeEdgeDto {
  return { id: `${source}->${target}`, source, target, kind: "emitted", status: null };
}

const OPTIONS = { width: 1200, height: 800, iterations: 120 };

describe("connectome force layout", () => {
  it("places identical data identically, so the map does not reshuffle", () => {
    const nodes = [node("a"), node("b"), node("c"), node("d")];
    const edges = [edge("a", "b"), edge("b", "c"), edge("c", "d")];

    const first = createSimulation(nodes, edges, OPTIONS);
    const second = createSimulation(nodes, edges, OPTIONS);

    for (let index = 0; index < first.length; index += 1) {
      expect(first[index].id).toBe(second[index].id);
      expect(first[index].x).toBeCloseTo(second[index].x, 6);
      expect(first[index].y).toBeCloseTo(second[index].y, 6);
    }
  });

  it("keeps every node inside a sane band around the canvas", () => {
    const nodes = Array.from({ length: 24 }, (_, index) => node(`n${index}`));
    const edges = nodes.slice(1).map((current, index) =>
      edge(nodes[index].id, current.id),
    );

    const placed = createSimulation(nodes, edges, OPTIONS);
    for (const item of placed) {
      expect(Number.isFinite(item.x)).toBe(true);
      expect(Number.isFinite(item.y)).toBe(true);
      // Pulled toward the centre, so nothing should fly to the far corners.
      expect(Math.abs(item.x - OPTIONS.width / 2)).toBeLessThan(OPTIONS.width);
      expect(Math.abs(item.y - OPTIONS.height / 2)).toBeLessThan(OPTIONS.height);
    }
  });

  it("separates coincident nodes instead of leaving them stacked", () => {
    const nodes = [node("same-a"), node("same-b")];
    const placed = createSimulation(nodes, [], { width: 800, height: 600, iterations: 200 });
    const distance = Math.hypot(placed[0].x - placed[1].x, placed[0].y - placed[1].y);
    expect(distance).toBeGreaterThan(1);
  });

  it("handles an empty graph without producing NaN bounds", () => {
    const placed = createSimulation([], [], OPTIONS);
    expect(placed).toEqual([]);
    const bounds = boundsOf(placed);
    expect(Number.isFinite(bounds.minX)).toBe(true);
    expect(Number.isFinite(bounds.maxY)).toBe(true);
  });

  it("finds the real neighbourhood of a node in both directions", () => {
    const edges = [edge("a", "b"), edge("b", "c")];
    expect(neighboursOf(edges, "b")).toEqual(new Set(["a", "c"]));
    expect(neighboursOf(edges, "a")).toEqual(new Set(["b"]));
    expect(neighboursOf(edges, "zzz")).toEqual(new Set());
  });

  it("fills a tall narrow frame instead of squatting in the middle", () => {
    // A square-ish cloud on a phone-shaped canvas: the height has to be used,
    // or the graph is a small square adrift in empty space.
    const points = [
      { x: 0, y: 0 },
      { x: 10, y: 10 },
      { x: 5, y: 9 },
    ];
    normaliseToFrame(points, 320, 640);
    const bounds = boundsOf(points);
    expect(bounds.maxX - bounds.minX).toBeGreaterThan(250);
    expect(bounds.maxY - bounds.minY).toBeGreaterThan(400);
    expect(bounds.maxX).toBeLessThanOrEqual(320);
    expect(bounds.maxY).toBeLessThanOrEqual(640);
  });

  it("keeps the axes from being stretched absurdly far apart", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 10, y: 10 },
    ];
    normaliseToFrame(points, 300, 3000, 0.88, 1.7);
    const bounds = boundsOf(points);
    const usedX = bounds.maxX - bounds.minX;
    const usedY = bounds.maxY - bounds.minY;
    // A 10x taller frame cannot make a square graph 10x taller; the cap holds.
    expect(usedY / usedX).toBeLessThan(1.8);
  });

  it("stays inside a wide frame", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 10, y: 4 },
      { x: 5, y: 9 },
    ];
    normaliseToFrame(points, 800, 400);
    const bounds = boundsOf(points);
    expect(bounds.maxX).toBeLessThanOrEqual(800);
    expect(bounds.maxY).toBeLessThanOrEqual(400);
    expect(bounds.minX).toBeGreaterThanOrEqual(0);
    expect(bounds.minY).toBeGreaterThanOrEqual(0);
  });

  it("leaves a single node alone instead of dividing by zero", () => {
    const points = [{ x: 3, y: 4 }];
    normaliseToFrame(points, 800, 400);
    expect(Number.isFinite(points[0].x)).toBe(true);
  });

  it("keeps the laid-out graph inside the canvas after fitting", () => {
    const nodes = Array.from({ length: 10 }, (_, index) => node(`n${index}`));
    const placed = createSimulation(nodes, [], { width: 900, height: 500, iterations: 120 });
    for (const item of placed) {
      expect(item.x).toBeGreaterThanOrEqual(-1);
      expect(item.x).toBeLessThanOrEqual(901);
      expect(item.y).toBeGreaterThanOrEqual(-1);
      expect(item.y).toBeLessThanOrEqual(501);
    }
  });

  it("scales radius with real weight and keeps it restrained", () => {
    const small = radiusFor({ ...node("a", 0), weight: 0 });
    const large = radiusFor({ ...node("a", 1), weight: 1 });
    expect(large).toBeGreaterThan(small);
    // Never a disc that swallows its neighbours.
    expect(large).toBeLessThan(20);
  });
});
