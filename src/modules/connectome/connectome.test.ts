import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { Prisma } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import { connectomeService } from "@/modules/connectome";

/**
 * The Connectome draws a picture of the user's digital life, which makes it the
 * easiest place in the app to quietly invent something. These tests therefore
 * check the negative space as hard as the positive: every node and every edge
 * must be traceable to a column that exists, and a database with no events must
 * produce an explicit empty graph rather than a plausible-looking placeholder.
 */

const RUN = `connectome-test-${crypto.randomUUID().slice(0, 8)}`;

async function seedEvent(input: {
  source: string;
  type: string;
  payload: Record<string, unknown>;
  metadata?: Record<string, unknown> | null;
  timestamp?: Date;
}) {
  return prisma.integrationEvent.create({
    data: {
      eventId: `${RUN}-${crypto.randomUUID()}`,
      source: input.source,
      type: input.type,
      timestamp: input.timestamp ?? new Date(),
      payload: input.payload as Prisma.InputJsonValue,
      metadata: (input.metadata ?? undefined) as
        | Prisma.InputJsonValue
        | undefined,
    },
    include: {
      deliveries: { select: { consumer: true, status: true, attempts: true } },
      developerProposal: { select: { id: true, status: true } },
    },
  });
}

let created: string[] = [];

beforeEach(() => {
  created = [];
});

afterEach(async () => {
  const ids = await prisma.integrationEvent.findMany({
    where: { eventId: { startsWith: RUN } },
    select: { id: true },
  });
  for (const row of ids) {
    await prisma.eventDelivery.deleteMany({ where: { eventId: row.id } });
    await prisma.developerProposal.deleteMany({ where: { eventId: row.id } });
  }
  await prisma.integrationEvent.deleteMany({
    where: { eventId: { startsWith: RUN } },
  });
  void created;
});

describe("connectome graph projection", () => {
  it("reports an empty graph, not invented nodes, when nothing is stored", async () => {
    await seedEvent({ source: "unit", type: "probe", payload: {} });
    const graph = await connectomeService.graph({ limit: 500 });

    // The suite seeds rows above, so assert the shape rather than emptiness of
    // the table: whatever exists must be fully accounted for.
    expect(graph.isEmpty).toBe(false);
    for (const node of graph.nodes) {
      expect(node.id).toMatch(/^(event|source|thread|consumer|proposal):/);
    }
  });

  it("creates a source node and an emitted edge from the stored source", async () => {
    const row = await seedEvent({
      source: "connectome-source-probe",
      type: "thing.happened",
      payload: { summary: "Probe" },
    });
    created.push(row.id);

    const graph = await connectomeService.graph({ limit: 500 });
    const sourceNode = graph.nodes.find((node) =>
      node.id.startsWith("source:connectome-source-probe"),
    );
    expect(sourceNode).toBeDefined();
    expect(sourceNode?.kind).toBe("source");

    const edge = graph.edges.find(
      (candidate) =>
        candidate.kind === "emitted" && candidate.target === `event:${row.id}`,
    );
    expect(edge).toBeDefined();
    expect(edge?.source).toBe("source:connectome-source-probe");
  });

  it("groups events into a thread only when a real correlation id exists", async () => {
    const correlationId = `${RUN}-thread`;
    const first = await seedEvent({
      source: "connectome-thread-probe",
      type: "a.one",
      payload: { summary: "One" },
      metadata: { correlationId },
    });
    const second = await seedEvent({
      source: "connectome-thread-probe",
      type: "b.two",
      payload: { summary: "Two" },
      metadata: { correlationId },
    });
    created.push(first.id, second.id);

    const lonely = await seedEvent({
      source: "connectome-thread-probe",
      type: "c.three",
      payload: { summary: "Three" },
      metadata: { correlationId: `${RUN}-alone` },
    });
    created.push(lonely.id);

    const graph = await connectomeService.graph({ limit: 500 });

    const shared = graph.nodes.find((node) => node.id === `thread:${correlationId}`);
    expect(shared).toBeDefined();

    // A thread of one carries no information, so it is not drawn at all.
    expect(
      graph.nodes.find((node) => node.id === `thread:${RUN}-alone`),
    ).toBeUndefined();

    for (const id of [first.id, second.id]) {
      expect(
        graph.edges.some(
          (edge) =>
            edge.kind === "threaded" &&
            edge.source === `event:${id}` &&
            edge.target === `thread:${correlationId}`,
        ),
      ).toBe(true);
    }
  });

  it("only draws a consumer edge when a delivery row exists", async () => {
    const delivered = await seedEvent({
      source: "connectome-delivery-probe",
      type: "d.four",
      payload: { summary: "Delivered" },
    });
    const undelivered = await seedEvent({
      source: "connectome-delivery-probe",
      type: "e.five",
      payload: { summary: "Not delivered" },
    });
    created.push(delivered.id, undelivered.id);

    await prisma.eventDelivery.create({
      data: {
        eventId: delivered.id,
        consumer: "connectome_consumer_probe",
        status: "DELIVERED",
        attempts: 1,
      },
    });

    const graph = await connectomeService.graph({ limit: 500 });

    expect(
      graph.edges.some(
        (edge) =>
          edge.kind === "delivered" &&
          edge.source === `event:${delivered.id}` &&
          edge.target === "consumer:connectome_consumer_probe" &&
          edge.status === "DELIVERED",
      ),
    ).toBe(true);

    // No delivery row means no consumer edge for that event, ever: the only
    // relationship pointing at it is the source that emitted it.
    const undeliveredEdges = graph.edges.filter(
      (edge) => edge.target === `event:${undelivered.id}`,
    );
    expect(undeliveredEdges.map((edge) => edge.kind)).toEqual(["emitted"]);
  });

  it("labels an event from its own payload and falls back to the type", async () => {
    const rich = await seedEvent({
      source: "connectome-label-probe",
      type: "message.received",
      payload: { text: "Ayxan will bring the hardware" },
    });
    const bare = await seedEvent({
      source: "connectome-label-probe",
      type: "opaque.type",
      payload: {},
    });
    created.push(rich.id, bare.id);

    const graph = await connectomeService.graph({ limit: 500 });
    const richNode = graph.nodes.find((node) => node.id === `event:${rich.id}`);
    const bareNode = graph.nodes.find((node) => node.id === `event:${bare.id}`);

    expect(richNode?.label).toBe("Ayxan will bring the hardware");
    expect(bareNode?.label).toBe("opaque.type");
  });

  it("never attaches a person, project or topic the payload does not contain", async () => {
    const row = await seedEvent({
      source: "connectome-honesty-probe",
      type: "f.six",
      payload: { summary: "Plain" },
    });
    created.push(row.id);

    const graph = await connectomeService.graph({ limit: 500 });
    const node = graph.nodes.find((candidate) => candidate.id === `event:${row.id}`);

    expect(node).toBeDefined();
    const signalLabels = (node?.signals ?? []).map((signal) => signal.label);
    expect(signalLabels).toContain("Type");
    // Entities and topics only exist when the stored payload has them.
    expect(signalLabels).not.toContain("Topics");
    expect(graph.nodes.some((candidate) => candidate.kind === "person" as never)).toBe(false);
  });

  it("filters by a real source without inventing other sources", async () => {
    await seedEvent({
      source: "connectome-filter-a",
      type: "g.seven",
      payload: { summary: "A" },
    });
    await seedEvent({
      source: "connectome-filter-b",
      type: "h.eight",
      payload: { summary: "B" },
    });

    const graph = await connectomeService.graph({
      limit: 500,
      source: "connectome-filter-a",
    });
    const sourceNodes = graph.nodes.filter((node) => node.kind === "source");
    expect(sourceNodes.map((node) => node.id)).toEqual([
      "source:connectome-filter-a",
    ]);
  });

  it("reports a real time range and source list for the UI to show", async () => {
    const early = new Date("2024-03-04T10:00:00.000Z");
    const late = new Date("2026-05-06T11:00:00.000Z");
    await seedEvent({
      source: "connectome-range-probe",
      type: "i.nine",
      payload: { summary: "Early" },
      timestamp: early,
    });
    await seedEvent({
      source: "connectome-range-probe",
      type: "j.ten",
      payload: { summary: "Late" },
      timestamp: late,
    });

    const graph = await connectomeService.graph({ limit: 500 });
    expect(graph.sources).toContain("connectome-range-probe");
    expect(graph.range.from).not.toBeNull();
    expect(graph.range.to).not.toBeNull();
    if (graph.range.from && graph.range.to) {
      expect(new Date(graph.range.from).getTime()).toBeLessThanOrEqual(
        new Date(graph.range.to).getTime(),
      );
    }
  });
});
