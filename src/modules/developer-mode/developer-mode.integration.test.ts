import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { prisma } from "@/lib/prisma";
import { createNormalizedEvent, integrationEventService } from "@/modules/events";
import { eventDeliveryService } from "@/modules/events";
import { developerModeService } from "@/modules/developer-mode";
import {
  DEVELOPER_MODE_SETTING_KEY,
  developerBugDetectedPayloadSchema,
} from "@/modules/developer-mode";
import { requireDesktopClient } from "@/lib/api/platform";

const exactMessage = "  user may be undefined <before> user.email — Unicode: Əli  ";

function bugEvent(id = `developer-bug-${crypto.randomUUID()}`) {
  return createNormalizedEvent({
    id,
    source: "core_brain",
    type: "developer.bug_detected",
    payload: {
      repository: "digital-brain",
      file: "src/auth/login.ts",
      line: 42,
      column: 10,
      title: "Possible null reference",
      message: exactMessage,
      severity: "warning",
      context: { source: "core-brain" },
    },
  });
}

/**
 * The exact payload Core Brain puts on a `developer.bug_detected` event.
 *
 * This is a contract fixture, not a convenience: Core requires the identity,
 * confidence and correlation keys, so a schema that omits them rejects every
 * real Brain finding.
 */
const brainBugDetectedPayload = () => ({
  event_id: `bf_${crypto.randomUUID()}`,
  finding_id: `bf_${crypto.randomUUID()}`,
  repository: "digital-brain",
  file: "src/auth/login.ts",
  line: 42,
  column: 10,
  title: "Possible null reference",
  message: "user may be undefined before use",
  severity: "high",
  confidence: 0.72,
  correlation_id: `corr_${crypto.randomUUID()}`,
  check: "null-safety",
  suggested_fix: "guard the lookup",
});

describe("Core Brain developer event contract", () => {
  it("accepts the payload Core actually emits", () => {
    expect(() =>
      developerBugDetectedPayloadSchema.parse(brainBugDetectedPayload()),
    ).not.toThrow();
  });

  it("accepts every severity on the Core ladder", () => {
    for (const severity of ["info", "warning", "high", "critical"] as const) {
      const parsed = developerBugDetectedPayloadSchema.parse({
        ...brainBugDetectedPayload(),
        severity,
      });
      expect(parsed.severity).toBe(severity);
    }
  });

  it("still rejects a payload that drifted away from the contract", () => {
    expect(() =>
      developerBugDetectedPayloadSchema.parse({
        ...brainBugDetectedPayload(),
        not_a_brain_field: true,
      }),
    ).toThrow();
  });

  it("still requires the fields Product projects on", () => {
    const payload = brainBugDetectedPayload();
    expect(() =>
      developerBugDetectedPayloadSchema.parse({
        event_id: payload.event_id,
        finding_id: payload.finding_id,
      }),
    ).toThrow();
  });
});

beforeEach(async () => {
  await prisma.automationRun.deleteMany();
  await prisma.actionExecution.deleteMany();
  await prisma.automation.deleteMany();
  await prisma.permission.deleteMany();
  await prisma.developerProposal.deleteMany();
  await prisma.integrationEvent.deleteMany();
  await prisma.appSetting.deleteMany({
    where: { key: DEVELOPER_MODE_SETTING_KEY },
  });
  await prisma.task.deleteMany();
  await prisma.calendarEvent.deleteMany();
  await prisma.job.deleteMany();
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.FLY_EVENTS_URL;
  delete process.env.FLY_API_TOKEN;
});

afterAll(async () => {
  await prisma.$disconnect();
});

describe("Developer Mode and shared Developer Information", () => {
  it("defaults to OFF and can be enabled and disabled", async () => {
    expect(await developerModeService.isEnabled()).toBe(false);
    expect(await developerModeService.setEnabled(true)).toEqual({ enabled: true });
    expect(await developerModeService.isEnabled()).toBe(true);
    expect(await developerModeService.setEnabled(false)).toEqual({ enabled: false });
    expect(await developerModeService.isEnabled()).toBe(false);
  });

  it("receives bug_detected information while mode is off without breaking event delivery", async () => {
    const event = bugEvent();
    const published = await integrationEventService.publish(event, ["fly"]);
    await developerModeService.projectBugDetected(event);

    expect(published.duplicate).toBe(false);
    expect(
      await prisma.eventDelivery.count({
        where: {
          consumer: "fly",
          event: { eventId: published.event.eventId },
        },
      }),
    ).toBe(1);

    const [information] = await developerModeService.listInformation();
    expect(information.eventId).toBe(event.id);
    expect(information.proposal).toMatchObject({
      repository: "digital-brain",
      file: "src/auth/login.ts",
      line: 42,
      severity: "warning",
      status: "PENDING",
    });
    expect(await prisma.actionExecution.count()).toBe(0);
  });

  it("preserves Core Brain title and message exactly in the display DTO", async () => {
    const event = bugEvent();
    await integrationEventService.publish(event, ["fly"]);
    await developerModeService.projectBugDetected(event);

    const [information] = await developerModeService.listInformation();
    expect(information.proposal?.title).toBe("Possible null reference");
    expect(information.proposal?.message).toBe(exactMessage);
    expect(information.payload.message).toBe(exactMessage);
  });

  it("rejects malformed developer events safely", () => {
    expect(() =>
      developerBugDetectedPayloadSchema.parse({
        repository: "digital-brain",
        file: "src/auth/login.ts",
        title: "Missing Core Brain explanation",
        severity: "warning",
      }),
    ).toThrow();
  });

  it("approves or rejects a proposal without executing any action", async () => {
    const event = bugEvent();
    await integrationEventService.publish(event, ["fly"]);
    await developerModeService.projectBugDetected(event);
    const [proposal] = await developerModeService.listProposals();

    await expect(
      developerModeService.approve(proposal.id, "local-user"),
    ).rejects.toMatchObject({ code: "DEVELOPER_MODE_DISABLED" });

    await developerModeService.setEnabled(true);
    const approved = await developerModeService.approve(
      proposal.id,
      "local-user",
      "Accepted for a future workflow",
    );
    expect(approved.status).toBe("APPROVED");
    expect(await prisma.actionExecution.count()).toBe(0);
    expect(await prisma.task.count()).toBe(0);

    await expect(
      developerModeService.reject(proposal.id, "local-user"),
    ).rejects.toMatchObject({ code: "DEVELOPER_PROPOSAL_ALREADY_DECIDED" });
  });

  it("keeps shared information available while blocking desktop controls on mobile", async () => {
    const mobileRequest = new Request("http://localhost/api/developer-mode", {
      headers: { "x-product-client-platform": "mobile" },
    });
    expect(() => requireDesktopClient(mobileRequest)).toThrow();

    const event = bugEvent();
    await integrationEventService.publish(event, ["fly"]);
    await developerModeService.projectBugDetected(event);
    expect(await developerModeService.listInformation()).toHaveLength(1);
  });

  it("forwards the unchanged event through the existing Fly delivery interface", async () => {
    process.env.FLY_EVENTS_URL = "https://fly.example.test/events";
    process.env.FLY_API_TOKEN = "fly-test-token";
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const event = bugEvent();
    const published = await integrationEventService.publish(event, ["fly"]);
    await eventDeliveryService.deliverEventId(published.event.eventId);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("https://fly.example.test/events");
    expect(init.headers).toMatchObject({
      "idempotency-key": event.id,
      authorization: "Bearer fly-test-token",
    });
    expect(JSON.parse(String(init.body))).toEqual(event);
    expect(
      await prisma.eventDelivery.findFirst({
        where: {
          consumer: "fly",
          event: { eventId: published.event.eventId },
        },
      }),
    ).toMatchObject({ status: "DELIVERED" });
  });
});
