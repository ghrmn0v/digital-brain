import "server-only";

import { z } from "zod";
import type { JsonObject, JsonValue } from "@/lib/events";
import { ApiError } from "@/lib/api/errors";
import {
  calendarEventCreateSchema,
  calendarEventUpdateSchema,
  calendarService,
} from "@/modules/calendar";
import { jobService } from "@/modules/jobs";
import {
  taskCreateSchema,
  taskService,
  taskUpdateSchema,
} from "@/modules/tasks";

export interface ActionHandlerContext {
  executionId: string;
  source: string;
}

export type ActionHandler = (
  payload: JsonObject,
  context: ActionHandlerContext,
) => Promise<JsonValue>;

const taskUpdateActionSchema = z
  .object({
    taskId: z.string().min(1).max(64),
    changes: taskUpdateSchema,
  })
  .strict();

const taskIdActionSchema = z
  .object({ taskId: z.string().min(1).max(64) })
  .strict();

const calendarUpdateActionSchema = z
  .object({
    eventId: z.string().min(1).max(64),
    changes: calendarEventUpdateSchema,
  })
  .strict();

const jobIdActionSchema = z
  .object({ jobId: z.string().min(1).max(64) })
  .strict();

function asJsonValue(value: unknown): JsonValue {
  return value as JsonValue;
}

export const actionHandlers: Readonly<Record<string, ActionHandler>> = {
  "tasks.create_task": async (payload, context) => {
    const parsed = taskCreateSchema.parse({
      ...payload,
      source: context.source,
    });
    return asJsonValue(await taskService.create(parsed));
  },

  "tasks.update_task": async (payload) => {
    const parsed = taskUpdateActionSchema.parse(payload);
    return asJsonValue(
      await taskService.update(parsed.taskId, parsed.changes),
    );
  },

  "tasks.complete_task": async (payload) => {
    const parsed = taskIdActionSchema.parse(payload);
    return asJsonValue(
      await taskService.update(parsed.taskId, { status: "done" }),
    );
  },

  "tasks.delete_task": async (payload) => {
    const parsed = taskIdActionSchema.parse(payload);
    await taskService.remove(parsed.taskId);
    return { deleted: true };
  },

  "calendar.create_event": async (payload, context) => {
    const parsed = calendarEventCreateSchema.parse({
      ...payload,
      source: context.source,
    });
    return asJsonValue(await calendarService.create(parsed));
  },

  "calendar.update_event": async (payload) => {
    const parsed = calendarUpdateActionSchema.parse(payload);
    return asJsonValue(
      await calendarService.update(parsed.eventId, parsed.changes),
    );
  },

  "calendar.delete_event": async (payload, context) => {
    const eventId = z.string().min(1).max(64).parse(payload.eventId);
    await calendarService.remove(eventId);
    return { deleted: true, source: context.source };
  },

  "jobs.save_job": async (payload) => {
    const parsed = jobIdActionSchema.parse(payload);
    return asJsonValue(await jobService.update(parsed.jobId, { status: "saved" }));
  },

  "jobs.ignore_job": async (payload) => {
    const parsed = jobIdActionSchema.parse(payload);
    return asJsonValue(
      await jobService.update(parsed.jobId, { status: "ignored" }),
    );
  },

  "jobs.apply_job": async () => {
    throw new ApiError(
      501,
      "EXTERNAL_JOB_APPLICATION_NOT_CONFIGURED",
      "External job application is not configured.",
    );
  },
};
