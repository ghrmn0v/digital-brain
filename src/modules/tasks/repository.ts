import "server-only";

import { randomUUID } from "node:crypto";
import { Prisma, type Task } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type {
  TaskCreateInput,
  TaskListQuery,
  TaskUpdateInput,
} from "@/modules/tasks/contracts";

function buildWhere(query: TaskListQuery): Prisma.TaskWhereInput {
  const where: Prisma.TaskWhereInput = {};

  if (query.status) where.status = query.status.toUpperCase() as Task["status"];
  if (query.priority) {
    where.priority = query.priority.toUpperCase() as Task["priority"];
  }
  if (query.q) {
    where.OR = [
      { title: { contains: query.q } },
      { description: { contains: query.q } },
    ];
  }

  return where;
}

function toCreateData(input: TaskCreateInput): Prisma.TaskCreateInput {
  const status = input.status.toUpperCase() as Task["status"];

  return {
    title: input.title,
    description: input.description,
    status,
    completedAt: status === "DONE" ? new Date() : null,
    priority: input.priority.toUpperCase() as Task["priority"],
    dueAt: input.dueAt ? new Date(input.dueAt) : input.dueAt,
    recurrenceRule: input.recurrenceRule,
    seriesId: input.recurrenceRule ? (input.seriesId ?? randomUUID()) : undefined,
    source: input.source,
    externalId: input.externalId,
    metadata: input.metadata as Prisma.InputJsonValue | undefined,
  };
}

function toUpdateData(input: TaskUpdateInput): Prisma.TaskUpdateInput {
  const data: Prisma.TaskUpdateInput = {};

  if (input.title !== undefined) data.title = input.title;
  if (input.description !== undefined) data.description = input.description;
  if (input.status !== undefined) {
    data.status = input.status.toUpperCase() as Task["status"];
    if (input.status !== "done") data.completedAt = null;
  }
  if (input.priority !== undefined) {
    data.priority = input.priority.toUpperCase() as Task["priority"];
  }
  if (input.dueAt !== undefined) {
    data.dueAt = input.dueAt === null ? null : new Date(input.dueAt);
  }
  if (input.recurrenceRule !== undefined) {
    data.recurrenceRule = input.recurrenceRule;
  }
  if (input.source !== undefined) data.source = input.source;
  if (input.externalId !== undefined) data.externalId = input.externalId;
  if (input.metadata !== undefined) {
    data.metadata = input.metadata as Prisma.InputJsonValue;
  }

  return data;
}

export const taskRepository = {
  async list(query: TaskListQuery, page: number, limit: number) {
    const where = buildWhere(query);
    const [items, total] = await prisma.$transaction([
      prisma.task.findMany({
        where,
        orderBy: [{ status: "asc" }, { dueAt: "asc" }, { createdAt: "desc" }],
        skip: (page - 1) * limit,
        take: limit,
      }),
      prisma.task.count({ where }),
    ]);

    return { items, total };
  },

  findById(id: string) {
    return prisma.task.findUnique({ where: { id } });
  },

  create(input: TaskCreateInput) {
    return prisma.task.create({ data: toCreateData(input) });
  },

  update(id: string, input: TaskUpdateInput) {
    return prisma.task.update({ where: { id }, data: toUpdateData(input) });
  },

  delete(id: string) {
    return prisma.task.delete({ where: { id } });
  },

  async completeWithRecurring(
    id: string,
    input: TaskUpdateInput,
    nextTask?: TaskCreateInput,
  ) {
    return prisma.$transaction(async (transaction) => {
      const task = await transaction.task.update({
        where: { id },
        data: {
          ...toUpdateData(input),
          completedAt: new Date(),
        },
      });
      const recurringTask = nextTask
        ? await transaction.task.create({ data: toCreateData(nextTask) })
        : null;
      return { task, recurringTask };
    });
  },
};
