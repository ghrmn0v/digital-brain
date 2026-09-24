import { afterAll, beforeEach, describe, expect, it } from "vitest";
import { actionService } from "@/modules/actions";
import { permissionService } from "@/modules/permissions";
import { prisma } from "@/lib/prisma";
import { taskService } from "@/modules/tasks";

beforeEach(async () => {
  await prisma.automationRun.deleteMany();
  await prisma.actionExecution.deleteMany();
  await prisma.permission.deleteMany();
  await prisma.task.deleteMany();
  await prisma.calendarEvent.deleteMany();
  await prisma.job.deleteMany();
  await prisma.integrationEvent.deleteMany();
});

afterAll(async () => {
  await prisma.$disconnect();
});

describe("permission-aware task actions", () => {
  it("executes AUTOMATIC actions immediately", async () => {
    await permissionService.upsert({
      source: "core_brain",
      action: "tasks.create_task",
      level: "AUTOMATIC",
      enabled: true,
    });

    const response = await actionService.request({
      source: "core_brain",
      action: "tasks.create_task",
      payload: { title: "Created by action engine" },
    });

    expect(response.status).toBe("completed");
    expect(response.success).toBe(true);
    const tasks = await taskService.list({}, 1, 20);
    expect(tasks.items).toHaveLength(1);
  });

  it("holds ASK_FIRST actions until approval", async () => {
    await permissionService.upsert({
      source: "core_brain",
      action: "tasks.create_task",
      level: "ASK_FIRST",
      enabled: true,
    });

    const pending = await actionService.request(
      {
        source: "core_brain",
        action: "tasks.create_task",
        payload: { title: "Needs approval" },
      },
      "ask-first-test",
    );
    expect(pending.status).toBe("pending_approval");

    const approved = await actionService.approve(
      pending.actionId,
      "local-user",
      "Approved in test",
    );
    expect(approved.status).toBe("completed");
    expect((await taskService.list({}, 1, 20)).items).toHaveLength(1);
  });

  it("rejects OFF actions without executing", async () => {
    await permissionService.upsert({
      source: "core_brain",
      action: "tasks.create_task",
      level: "OFF",
      enabled: true,
    });

    const response = await actionService.request({
      source: "core_brain",
      action: "tasks.create_task",
      payload: { title: "Must not be created" },
    });
    expect(response.status).toBe("rejected");
    expect((await taskService.list({}, 1, 20)).items).toHaveLength(0);
  });
});
