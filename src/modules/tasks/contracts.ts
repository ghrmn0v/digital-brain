import { z } from "zod";
import { isValidRecurrenceRule } from "@/lib/domain/recurrence";
import type { JsonValue } from "@/lib/events";

export const TASK_STATUSES = [
  "todo",
  "in_progress",
  "blocked",
  "done",
  "cancelled",
] as const;

export const TASK_PRIORITIES = ["low", "medium", "high", "urgent"] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];
export type TaskPriority = (typeof TASK_PRIORITIES)[number];

const optionalDate = z.iso.datetime({ offset: true }).nullable().optional();
const recurrenceRule = z
  .string()
  .max(128)
  .refine(isValidRecurrenceRule, "Use a supported RRULE value.");

export const taskCreateSchema = z
  .object({
    title: z.string().trim().min(1).max(200),
    description: z.string().trim().max(10_000).nullable().optional(),
    status: z.enum(TASK_STATUSES).default("todo"),
    priority: z.enum(TASK_PRIORITIES).default("medium"),
    dueAt: optionalDate,
    recurrenceRule: recurrenceRule.nullable().optional(),
    seriesId: z.uuid().optional(),
    source: z.string().trim().min(1).max(64).default("local"),
    externalId: z.string().trim().min(1).max(256).nullable().optional(),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict();

export const taskUpdateSchema = z
  .object({
    title: z.string().trim().min(1).max(200).optional(),
    description: z.string().trim().max(10_000).nullable().optional(),
    status: z.enum(TASK_STATUSES).optional(),
    priority: z.enum(TASK_PRIORITIES).optional(),
    dueAt: optionalDate,
    recurrenceRule: recurrenceRule.nullable().optional(),
    source: z.string().trim().min(1).max(64).optional(),
    externalId: z.string().trim().min(1).max(256).nullable().optional(),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict()
  .refine((value) => Object.keys(value).length > 0, {
    message: "At least one field must be provided.",
  });

export const taskListQuerySchema = z.object({
  q: z.string().trim().max(100).optional(),
  status: z.enum(TASK_STATUSES).optional(),
  priority: z.enum(TASK_PRIORITIES).optional(),
});

export type TaskCreateInput = z.infer<typeof taskCreateSchema>;
export type TaskUpdateInput = z.infer<typeof taskUpdateSchema>;
export type TaskListQuery = z.infer<typeof taskListQuerySchema>;

export interface TaskDto {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  dueAt: string | null;
  completedAt: string | null;
  recurrenceRule: string | null;
  seriesId: string | null;
  source: string;
  externalId: string | null;
  metadata: JsonValue | null;
  createdAt: string;
  updatedAt: string;
}
