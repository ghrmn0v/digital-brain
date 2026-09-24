import { afterAll, beforeEach, describe, expect, it } from "vitest";
import { prisma } from "@/lib/prisma";
import { createNormalizedEvent, integrationEventService } from "@/modules/events";
import { automationService } from "@/modules/automations";
import { jobService } from "@/modules/jobs";
import { permissionService } from "@/modules/permissions";
import { taskService } from "@/modules/tasks";

beforeEach(async () => {
  await prisma.automationRun.deleteMany();
  await prisma.actionExecution.deleteMany();
  await prisma.automation.deleteMany();
  await prisma.permission.deleteMany();
  await prisma.task.deleteMany();
  await prisma.calendarEvent.deleteMany();
  await prisma.job.deleteMany();
  await prisma.integrationEvent.deleteMany();
});

afterAll(async () => {
  await prisma.$disconnect();
});

describe("product integration flows", () => {
  it("preserves user job state during connector refresh", async () => {
    const first = await jobService.ingest({
      source: "linkedin",
      externalId: "job-1",
      title: "Engineer",
      company: "Acme",
      status: "seen",
    });
    await jobService.update(first.job.id, { status: "saved" });
    const refreshed = await jobService.ingest({
      source: "linkedin",
      externalId: "job-1",
      title: "Senior Engineer",
      company: "Acme",
      status: "seen",
    });

    expect(first.created).toBe(true);
    expect(refreshed.created).toBe(false);
    expect(refreshed.job.status).toBe("saved");
    expect(refreshed.job.title).toBe("Senior Engineer");
  });

  it("deduplicates normalized integration events", async () => {
    const event = createNormalizedEvent({
      source: "system",
      type: "test.event",
      id: "stable-test-event",
      payload: { value: 1 },
    });
    const first = await integrationEventService.publish(event, []);
    const second = await integrationEventService.publish(event, []);

    expect(first.duplicate).toBe(false);
    expect(second.duplicate).toBe(true);
    expect(await prisma.integrationEvent.count()).toBe(1);
  });

  it("routes automation actions through permissions", async () => {
    await permissionService.upsert({
      source: "automation",
      action: "tasks.create_task",
      level: "AUTOMATIC",
      enabled: true,
    });
    const automation = await automationService.create({
      name: "Create flagged task",
      enabled: true,
      triggerKind: "event",
      triggerValue: "message.flagged",
      conditions: [
        { path: "event.payload.createTask", operator: "eq", value: true },
      ],
      action: "tasks.create_task",
      actionPayload: { title: "Review {{event.payload.title}}" },
      cooldownSeconds: null,
    });
    const event = createNormalizedEvent({
      source: "whatsapp",
      type: "message.flagged",
      id: "automation-test-event",
      payload: { createTask: true, title: "invoice" },
    });

    await automationService.processEvent(event);
    const tasks = await taskService.list({}, 1, 20);
    expect(tasks.items[0]?.title).toBe("Review invoice");
    expect(
      await prisma.automationRun.findFirst({ where: { automationId: automation.id } }),
    ).toMatchObject({ status: "COMPLETED" });
  });
});
