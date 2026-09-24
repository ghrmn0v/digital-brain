import "server-only";

import { randomUUID } from "node:crypto";
import type { Task } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import { getNextOccurrence } from "@/lib/domain/recurrence";
import type { JsonValue } from "@/lib/events";
import {
  type TaskCreateInput,
  type TaskDto,
  type TaskListQuery,
  type TaskPriority,
  type TaskStatus,
  type TaskUpdateInput,
} from "@/modules/tasks/contracts";
import { taskRepository } from "@/modules/tasks/repository";

function toTaskDto(task: Task): TaskDto {
  return {
    id: task.id,
    title: task.title,
    description: task.description,
    status: task.status.toLowerCase() as TaskStatus,
    priority: task.priority.toLowerCase() as TaskPriority,
    dueAt: task.dueAt?.toISOString() ?? null,
    completedAt: task.completedAt?.toISOString() ?? null,
    recurrenceRule: task.recurrenceRule,
    seriesId: task.seriesId,
    source: task.source,
    externalId: task.externalId,
    metadata: (task.metadata as JsonValue | null) ?? null,
    createdAt: task.createdAt.toISOString(),
    updatedAt: task.updatedAt.toISOString(),
  };
}

function assertFound(task: Task | null): asserts task is Task {
  if (!task) {
    throw new ApiError(404, "TASK_NOT_FOUND", "Task not found.");
  }
}

function createNextRecurringTask(task: Task): TaskCreateInput | undefined {
  if (!task.recurrenceRule || !task.dueAt) return undefined;

  const metadata =
    task.metadata &&
    typeof task.metadata === "object" &&
    !Array.isArray(task.metadata)
      ? (task.metadata as Record<string, JsonValue>)
      : undefined;

  return {
    title: task.title,
    description: task.description,
    status: "todo",
    priority: task.priority.toLowerCase() as TaskPriority,
    dueAt: getNextOccurrence(task.dueAt, task.recurrenceRule).toISOString(),
    recurrenceRule: task.recurrenceRule,
    seriesId: task.seriesId ?? randomUUID(),
    source: task.source,
    externalId: null,
    metadata,
  };
}

export const taskService = {
  async list(query: TaskListQuery, page: number, limit: number) {
    const { items, total } = await taskRepository.list(query, page, limit);
    return {
      items: items.map(toTaskDto),
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    };
  },

  async get(id: string) {
    const task = await taskRepository.findById(id);
    assertFound(task);
    return toTaskDto(task);
  },

  async create(input: TaskCreateInput) {
    const normalized: TaskCreateInput = {
      ...input,
      dueAt: input.dueAt ?? null,
      description: input.description ?? null,
      recurrenceRule: input.recurrenceRule ?? null,
      externalId: input.externalId ?? null,
    };
    return toTaskDto(await taskRepository.create(normalized));
  },

  async update(id: string, input: TaskUpdateInput) {
    const current = await taskRepository.findById(id);
    assertFound(current);

    if (input.status === "done" && current.status !== "DONE") {
      const nextTask = createNextRecurringTask(current);
      const { task } = await taskRepository.completeWithRecurring(
        id,
        input,
        nextTask,
      );
      return toTaskDto(task);
    }

    return toTaskDto(await taskRepository.update(id, input));
  },

  async remove(id: string) {
    const current = await taskRepository.findById(id);
    assertFound(current);
    await taskRepository.delete(id);
  },
};
