import { describe, expect, it } from "vitest";
import type { ConnectomeNodeDto } from "@/modules/connectome";
import { measureLabel, placeLabels, shortenTo } from "@/components/connectome/labels";

/**
 * Unreadable text is worse than no text, so these tests pin the property that
 * makes the map legible: no two drawn labels may overlap, and the labels that
 * matter most are the ones that survive.
 */

function node(id: string, label: string, kind: ConnectomeNodeDto["kind"] = "event", weight = 0.5): ConnectomeNodeDto {
  return { id, kind, label, detail: null, occurredAt: null, weight, signals: [], href: null };
}

const radiusOf = () => 10;

describe("connectome label placement", () => {
  it("never places two labels on top of each other", () => {
    // Every node at the same spot is the worst case a force layout can produce.
    const nodes = Array.from({ length: 12 }, (_, index) =>
      node(`n${index}`, `Label number ${index}`),
    );
    const positions = new Map(nodes.map((n) => [n.id, { x: 400, y: 300 }]));

    const placed = placeLabels({ nodes, positions, radiusOf, emphasis: new Set() });

    const boxes = [...placed.values()];
    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const a = boxes[i];
        const b = boxes[j];
        const collides =
          a.x < b.x + b.width &&
          a.x + a.width > b.x &&
          a.y < b.y + b.height &&
          a.y + a.height > b.y;
        expect(collides, `${a.id} overlaps ${b.id}`).toBe(false);
      }
    }
  });

  it("keeps the emphasised nodes' labels and drops the rest", () => {
    const nodes = Array.from({ length: 20 }, (_, index) =>
      node(`n${index}`, `Event ${index}`),
    );
    const positions = new Map(nodes.map((n) => [n.id, { x: 300, y: 300 }]));

    const placed = placeLabels({
      nodes,
      positions,
      radiusOf,
      emphasis: new Set(["n17", "n18"]),
    });

    expect(placed.has("n17")).toBe(true);
    expect(placed.has("n18")).toBe(true);
  });

  it("prefers a structural node over an event when both would fit", () => {
    const nodes = [
      node("evt", "A long event label", "event", 0.9),
      node("src", "Whatsapp", "source", 0.2),
    ];
    const positions = new Map([
      ["evt", { x: 400, y: 300 }],
      ["src", { x: 400, y: 360 }],
    ]);

    const placed = placeLabels({ nodes, positions, radiusOf, emphasis: new Set() });
    expect(placed.has("src")).toBe(true);
  });

  it("is deterministic for the same input", () => {
    const nodes = Array.from({ length: 10 }, (_, index) => node(`n${index}`, `L${index}`));
    const positions = new Map(
      nodes.map((n, index) => [n.id, { x: 200 + index * 40, y: 200 }] as const),
    );
    const first = placeLabels({ nodes, positions, radiusOf, emphasis: new Set() });
    const second = placeLabels({ nodes, positions, radiusOf, emphasis: new Set() });
    expect([...first.keys()]).toEqual([...second.keys()]);
  });

  it("respects the label budget on a crowded graph", () => {
    const nodes = Array.from({ length: 60 }, (_, index) => node(`n${index}`, `Node ${index}`));
    const positions = new Map(
      nodes.map((n, index) => [n.id, { x: (index % 10) * 30, y: Math.floor(index / 10) * 30 }]),
    );
    const placed = placeLabels({
      nodes,
      positions,
      radiusOf,
      emphasis: new Set(),
      limit: 8,
    });
    expect(placed.size).toBeLessThanOrEqual(8);
  });

  it("refuses to draw a label that would hang over the edge", () => {
    const nodes = [node("edge", "A label right on the boundary")];
    // The node sits hard against the left edge, so the centred-below candidate
    // starts at a negative x and would overflow the page.
    const positions = new Map([["edge", { x: 6, y: 200 }]]);
    const placed = placeLabels({
      nodes,
      positions,
      radiusOf,
      emphasis: new Set(),
      bounds: { width: 400, height: 400 },
    });
    for (const box of placed.values()) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(400);
    }
  });

  it("draws a label that comfortably fits", () => {
    const nodes = [node("mid", "Fits fine")];
    const positions = new Map([["mid", { x: 200, y: 200 }]]);
    const placed = placeLabels({
      nodes,
      positions,
      radiusOf,
      emphasis: new Set(),
      bounds: { width: 400, height: 400 },
    });
    expect(placed.has("mid")).toBe(true);
  });

  it("keeps a long label whole when the room is there", () => {
    // The map used to cut every label at 25 characters, so a node sitting in
    // open space still read "Ayxan will bring the hack…" beside 300px of empty
    // canvas. Length is now the room's decision, not a global constant.
    const long = "Ayxan will bring the hackathon demo hardware on Thursday";
    expect(long.length).toBeGreaterThan(26);
    const placed = placeLabels({
      nodes: [node("solo", long)],
      positions: new Map([["solo", { x: 200, y: 200 }]]),
      radiusOf,
      emphasis: new Set(),
      bounds: { width: 900, height: 600 },
    });
    expect(placed.has("solo")).toBe(true);
    expect(placed.get("solo")!.width).toBe(measureLabel(long).width);
  });

  it("still shortens a label rather than overflowing the frame", () => {
    const placed = placeLabels({
      nodes: [node("edge", "Ayxan will bring the hackathon demo hardware on Thursday")],
      positions: new Map([["edge", { x: 4, y: 200 }]]),
      radiusOf,
      emphasis: new Set(),
      bounds: { width: 260, height: 400 },
    });
    for (const box of placed.values()) {
      expect(box.x + box.width).toBeLessThanOrEqual(260);
    }
  });

  it("never leaves a label ending in a half-written word", () => {
    // When the source has a space to cut on, the cut must use it.
    const sentences = [
      "Ayxan will bring the hackathon demo hardware on Thursday afternoon",
      "Principal Engineer, hackathon platform at Northwind Labs",
      "Possible null reference on the connectome timeline renderer",
    ];
    for (const text of sentences) {
      for (const limit of [44, 34, 26]) {
        const out = shortenTo(text, limit);
        if (out === text) continue;
        expect(out.endsWith("…"), `${limit}: ${out}`).toBe(true);
        const body = out.slice(0, -1);
        expect(text.startsWith(body), `${limit}: ${out}`).toBe(true);
        // The cut lands on a boundary and trailing punctuation is then tidied
        // away, so what follows is a space *or* the punctuation that was
        // stripped — "Principal Engineer," shortens to "Principal Engineer…".
        expect(/[\s,;:.-]/.test(text[body.length] ?? ""), `${limit}: ${out}`).toBe(true);
      }
    }
  });

  it("marks the cut when a label is one unbroken token with nowhere to break", () => {
    // There is no word boundary inside a 53-character token, so the cut is hard.
    // What matters is that it is marked, so it cannot be read as complete.
    const monster = "supercalifragilisticexpialidociousandthensomemorewords";
    const out = shortenTo(monster, 26);
    expect(out.endsWith("…")).toBe(true);
    expect(monster.startsWith(out.slice(0, -1))).toBe(true);
  });

  it("returns short labels untouched", () => {
    expect(shortenTo("Core Brain", Number.POSITIVE_INFINITY)).toBe("Core Brain");
    expect(shortenTo("Core Brain", 26)).toBe("Core Brain");
  });

  it("measures a label wide enough to read and truncates very long ones", () => {
    expect(measureLabel("short").width).toBeLessThan(measureLabel("a much longer label").width);
    expect(measureLabel("x".repeat(400)).width).toBeLessThanOrEqual(190);
  });
});
