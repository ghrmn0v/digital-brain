import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { prisma } from "@/lib/prisma";
import { createNormalizedEvent, eventDeliveryService, integrationEventService } from "@/modules/events";

/**
 * The Brain answers a *semantically* rejected event with HTTP 200 and
 * `outcome: "rejected"` in the body: the request was handled, the event was not
 * stored. Treating any 2xx as success recorded those events as DELIVERED, so a
 * whole class of bad events disappeared without a trace.
 *
 * These tests pin the fix against a stub Brain rather than a live one, because
 * the point is the shape of the response, not the Brain.
 */

const CONSUMER = "core_brain";

function event(id = `delivery-semantics-${crypto.randomUUID()}`) {
  return createNormalizedEvent({
    id,
    source: "calendar",
    type: "event.created",
    payload: { summary: "Design review" },
  });
}

function brainSays(body: unknown, status = 200) {
  return vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

const INGEST_REJECTED = {
  ok: true,
  result: {
    outcome: "rejected",
    reason:
      "event 'source.calendar.event_created' requires a non-empty string payload field 'summary' for processing",
    event_id: "evt",
    user_id: "u",
    events_emitted: 0,
    memory_ids: [],
  },
  error: null,
};

const INGEST_ACCEPTED = {
  ok: true,
  result: {
    outcome: "accepted",
    event_id: "evt",
    user_id: "u",
    events_emitted: 1,
    memory_ids: ["mem_1"],
  },
  error: null,
};

async function deliverOne(fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetchMock);
  const published = await integrationEventService.publish(event(), [CONSUMER]);
  await eventDeliveryService.deliverEventId(published.event.eventId);
  return prisma.eventDelivery.findFirstOrThrow({
    where: { consumer: CONSUMER, event: { eventId: published.event.eventId } },
  });
}

describe("brain delivery outcome semantics", () => {
  beforeEach(async () => {
    process.env.CORE_BRAIN_URL = "http://brain.test/v1/brain";
    process.env.CORE_BRAIN_USER_ID = "usr_delivery";
    await prisma.eventDelivery.deleteMany();
    await prisma.integrationEvent.deleteMany();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.CORE_BRAIN_URL;
    delete process.env.CORE_BRAIN_USER_ID;
  });

  it("does not record a semantically rejected event as delivered", async () => {
    const delivery = await deliverOne(brainSays(INGEST_REJECTED));

    expect(delivery.status).not.toBe("DELIVERED");
    expect(delivery.status).toBe("FAILED");
    expect(delivery.lastError).toContain("did not accept");
    expect(delivery.lastError).toContain("rejected");
    expect(delivery.lastError).toContain("summary");
  });

  it("records an accepted event as delivered", async () => {
    const delivery = await deliverOne(brainSays(INGEST_ACCEPTED));

    expect(delivery.status).toBe("DELIVERED");
    expect(delivery.lastError).toBeNull();
  });

  it("records a duplicate as delivered, because the Brain did process it", async () => {
    const delivery = await deliverOne(
      brainSays({
        ok: true,
        result: {
          outcome: "duplicate",
          event_id: "evt",
          user_id: "u",
          events_emitted: 0,
          memory_ids: [],
        },
        error: null,
      }),
    );

    expect(delivery.status).toBe("DELIVERED");
  });

  it("does not retry a rejection, because retrying cannot fix the payload", async () => {
    const fetchMock = brainSays(INGEST_REJECTED);
    const delivery = await deliverOne(fetchMock);

    expect(delivery.attempts).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps a retryable 5xx pending for another attempt", async () => {
    const delivery = await deliverOne(brainSays({}, 503));

    expect(delivery.status).toBe("PENDING");
    expect(delivery.lastError).toContain("HTTP 503");
    expect(delivery.nextAttemptAt).not.toBeNull();
  });

  it("fails a non-retryable 4xx immediately", async () => {
    const delivery = await deliverOne(brainSays({}, 422));

    expect(delivery.status).toBe("FAILED");
    expect(delivery.lastError).toContain("HTTP 422");
  });

  it("fails an unrecognised outcome rather than assuming success", async () => {
    const delivery = await deliverOne(
      brainSays({ ok: true, result: { outcome: "quarantined_by_brain" } }),
    );

    expect(delivery.status).toBe("FAILED");
    expect(delivery.lastError).toContain("quarantined_by_brain");
  });

  it("ignores a non-JSON 2xx rather than failing a working delivery", async () => {
    const fetchMock = vi.fn(async () => new Response("ok", { status: 200 }));
    const delivery = await deliverOne(fetchMock as never);

    expect(delivery.status).toBe("DELIVERED");
  });

  it("ignores a 2xx body that is not an ingest response", async () => {
    const delivery = await deliverOne(
      brainSays({ behaviour: "IMPORTANT", priorityLevel: "HIGH" }),
    );

    expect(delivery.status).toBe("DELIVERED");
  });

  it("does not apply brain semantics to the fly consumer", async () => {
    process.env.FLY_EVENTS_URL = "http://fly.test/events";
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ result: { outcome: "rejected" } }),
          { status: 200, headers: { "content-type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const published = await integrationEventService.publish(event(), ["fly"]);
    await eventDeliveryService.deliverEventId(published.event.eventId);

    const delivery = await prisma.eventDelivery.findFirstOrThrow({
      where: { consumer: "fly", event: { eventId: published.event.eventId } },
    });
    expect(delivery.status).toBe("DELIVERED");
    delete process.env.FLY_EVENTS_URL;
  });
});
