import "server-only";

import { Prisma, type ActionExecution } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type { ActionExecutionListQuery } from "@/modules/actions/contracts";

export const actionExecutionRepository = {
  async list(query: ActionExecutionListQuery, page: number, limit: number) {
    const where: Prisma.ActionExecutionWhereInput = {};
    if (query.status) {
      where.status = query.status.toUpperCase() as ActionExecution["status"];
    }
    if (query.source) where.source = query.source;
    if (query.action) where.action = { contains: query.action };

    const [items, total] = await prisma.$transaction([
      prisma.actionExecution.findMany({
        where,
        orderBy: { requestedAt: "desc" },
        skip: (page - 1) * limit,
        take: limit,
      }),
      prisma.actionExecution.count({ where }),
    ]);
    return { items, total };
  },

  findById(id: string) {
    return prisma.actionExecution.findUnique({ where: { id } });
  },

  findByIdempotencyKey(key: string) {
    return prisma.actionExecution.findUnique({ where: { idempotencyKey: key } });
  },

  create(data: Prisma.ActionExecutionCreateInput) {
    return prisma.actionExecution.create({ data });
  },

  markRejected(
    id: string,
    data: {
      permissionLevel: ActionExecution["permissionLevel"];
      decidedBy?: string;
      decisionReason?: string;
    },
  ) {
    return prisma.actionExecution.update({
      where: { id },
      data: {
        status: "REJECTED",
        permissionLevel: data.permissionLevel,
        decidedBy: data.decidedBy,
        decisionReason: data.decisionReason,
        decidedAt: new Date(),
        completedAt: new Date(),
      },
    });
  },

  claimPending(
    id: string,
    version: number,
    data: { decidedBy: string; decisionReason?: string },
  ) {
    return prisma.actionExecution.updateMany({
      where: { id, status: "PENDING_APPROVAL", version },
      data: {
        decidedAt: new Date(),
        decidedBy: data.decidedBy,
        decisionReason: data.decisionReason,
        version: { increment: 1 },
      },
    });
  },

  rejectPending(
    id: string,
    version: number,
    data: { decidedBy: string; decisionReason?: string },
  ) {
    return prisma.actionExecution.updateMany({
      where: { id, status: "PENDING_APPROVAL", version },
      data: {
        status: "REJECTED",
        decidedAt: new Date(),
        completedAt: new Date(),
        decidedBy: data.decidedBy,
        decisionReason: data.decisionReason,
        version: { increment: 1 },
      },
    });
  },

  complete(
    id: string,
    result: Prisma.InputJsonValue,
    attempts: number,
  ) {
    return prisma.actionExecution.update({
      where: { id },
      data: {
        status: "COMPLETED",
        result,
        error: null,
        attempts,
        completedAt: new Date(),
      },
    });
  },

  fail(id: string, error: string, attempts: number) {
    return prisma.actionExecution.update({
      where: { id },
      data: {
        status: "FAILED",
        error,
        attempts,
        completedAt: new Date(),
      },
    });
  },

  syncAutomationRun(
    actionExecutionId: string,
    status: "COMPLETED" | "REJECTED" | "FAILED",
    error?: string,
  ) {
    return prisma.automationRun.updateMany({
      where: { actionExecutionId, status: "PENDING" },
      data: { status, error, completedAt: new Date() },
    });
  },
};
