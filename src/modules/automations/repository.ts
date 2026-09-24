import "server-only";

import { Prisma, type Automation } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type {
  AutomationCreateInput,
  AutomationListQuery,
  AutomationUpdateInput,
} from "@/modules/automations/contracts";

function toCreateData(input: AutomationCreateInput): Prisma.AutomationCreateInput {
  return {
    name: input.name,
    description: input.description,
    enabled: input.enabled,
    triggerKind: input.triggerKind.toUpperCase() as Automation["triggerKind"],
    triggerValue: input.triggerValue,
    conditions: input.conditions as unknown as Prisma.InputJsonValue,
    action: input.action,
    actionPayload: input.actionPayload as Prisma.InputJsonValue,
    cooldownSeconds: input.cooldownSeconds,
    nextRunAt: input.nextRunAt ? new Date(input.nextRunAt) : input.nextRunAt,
  };
}

function toUpdateData(input: AutomationUpdateInput): Prisma.AutomationUpdateInput {
  const data: Prisma.AutomationUpdateInput = {};
  if (input.name !== undefined) data.name = input.name;
  if (input.description !== undefined) data.description = input.description;
  if (input.enabled !== undefined) data.enabled = input.enabled;
  if (input.triggerKind !== undefined) {
    data.triggerKind = input.triggerKind.toUpperCase() as Automation["triggerKind"];
  }
  if (input.triggerValue !== undefined) data.triggerValue = input.triggerValue;
  if (input.conditions !== undefined) {
    data.conditions = input.conditions as unknown as Prisma.InputJsonValue;
  }
  if (input.action !== undefined) data.action = input.action;
  if (input.actionPayload !== undefined) {
    data.actionPayload = input.actionPayload as Prisma.InputJsonValue;
  }
  if (input.cooldownSeconds !== undefined) {
    data.cooldownSeconds = input.cooldownSeconds;
  }
  if (input.nextRunAt !== undefined) {
    data.nextRunAt = input.nextRunAt ? new Date(input.nextRunAt) : null;
  }
  return data;
}

export const automationRepository = {
  async list(query: AutomationListQuery) {
    const where: Prisma.AutomationWhereInput = {};
    if (query.enabled) where.enabled = query.enabled === "true";
    if (query.triggerKind) {
      where.triggerKind =
        query.triggerKind.toUpperCase() as Automation["triggerKind"];
    }
    return prisma.automation.findMany({ where, orderBy: { createdAt: "desc" } });
  },

  findById(id: string) {
    return prisma.automation.findUnique({ where: { id } });
  },

  listEventAutomations(type: string) {
    return prisma.automation.findMany({
      where: {
        enabled: true,
        triggerKind: "EVENT",
        OR: [{ triggerValue: type }, { triggerValue: "*" }],
      },
    });
  },

  listDueSchedules(now: Date) {
    return prisma.automation.findMany({
      where: {
        enabled: true,
        triggerKind: "SCHEDULE",
        nextRunAt: { lte: now },
      },
      take: 50,
    });
  },

  create(input: AutomationCreateInput) {
    return prisma.automation.create({ data: toCreateData(input) });
  },

  update(id: string, input: AutomationUpdateInput) {
    return prisma.automation.update({ where: { id }, data: toUpdateData(input) });
  },

  delete(id: string) {
    return prisma.automation.delete({ where: { id } });
  },

  markTriggered(id: string, lastError?: string) {
    return prisma.automation.update({
      where: { id },
      data: { lastRunAt: new Date(), lastError: lastError ?? null },
    });
  },

  clearSchedule(id: string) {
    return prisma.automation.update({ where: { id }, data: { nextRunAt: null } });
  },

  createRun(data: Prisma.AutomationRunCreateInput) {
    return prisma.automationRun.create({ data });
  },

  attachActionExecution(id: string, actionExecutionId: string) {
    return prisma.automationRun.update({
      where: { id },
      data: { actionExecutionId },
    });
  },

  completeRun(
    id: string,
    status: "COMPLETED" | "REJECTED" | "FAILED" | "SKIPPED",
    error?: string,
  ) {
    return prisma.automationRun.update({
      where: { id },
      data: { status, error, completedAt: new Date() },
    });
  },
};
