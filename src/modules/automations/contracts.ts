import { z } from "zod";
import type { JsonValue } from "@/lib/events";
import type { AutomationCondition } from "@/modules/automations/condition-evaluator";

export const AUTOMATION_TRIGGER_KINDS = ["event", "schedule", "manual"] as const;
export const AUTOMATION_RUN_STATUSES = [
  "pending",
  "completed",
  "rejected",
  "failed",
  "skipped",
] as const;

const conditionSchema = z
  .object({
    path: z.string().min(1).max(256),
    operator: z.enum([
      "eq",
      "neq",
      "contains",
      "not_contains",
      "gt",
      "gte",
      "lt",
      "lte",
      "exists",
      "in",
    ]),
    value: z.json().optional(),
  })
  .strict();

export const automationCreateSchema = z
  .object({
    name: z.string().trim().min(1).max(200),
    description: z.string().trim().max(2_000).nullable().optional(),
    enabled: z.boolean().default(false),
    triggerKind: z.enum(AUTOMATION_TRIGGER_KINDS).default("event"),
    triggerValue: z.string().trim().min(1).max(256).nullable().optional(),
    conditions: z.array(conditionSchema).max(50).default([]),
    action: z
      .string()
      .trim()
      .min(1)
      .max(128)
      .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/),
    actionPayload: z.record(z.string(), z.json()).default({}),
    cooldownSeconds: z.number().int().min(0).max(31_536_000).nullable().optional(),
    nextRunAt: z.iso.datetime({ offset: true }).nullable().optional(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.triggerKind === "event" && !value.triggerValue) {
      context.addIssue({
        code: "custom",
        path: ["triggerValue"],
        message: "Event automations require triggerValue.",
      });
    }
    if (value.triggerKind === "schedule") {
      if (!value.nextRunAt) {
        context.addIssue({
          code: "custom",
          path: ["nextRunAt"],
          message: "Schedule automations require nextRunAt.",
        });
      }
      if (new Date(value.nextRunAt as string) <= new Date()) {
        context.addIssue({
          code: "custom",
          path: ["nextRunAt"],
          message: "nextRunAt must be in the future.",
        });
      }
    }
  });

export const automationUpdateSchema = z
  .object({
    name: z.string().trim().min(1).max(200).optional(),
    description: z.string().trim().max(2_000).nullable().optional(),
    enabled: z.boolean().optional(),
    triggerKind: z.enum(AUTOMATION_TRIGGER_KINDS).optional(),
    triggerValue: z.string().trim().min(1).max(256).nullable().optional(),
    conditions: z.array(conditionSchema).max(50).optional(),
    action: z
      .string()
      .trim()
      .min(1)
      .max(128)
      .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/)
      .optional(),
    actionPayload: z.record(z.string(), z.json()).optional(),
    cooldownSeconds: z.number().int().min(0).max(31_536_000).nullable().optional(),
    nextRunAt: z.iso.datetime({ offset: true }).nullable().optional(),
  })
  .strict()
  .refine((value) => Object.keys(value).length > 0, {
    message: "At least one field must be provided.",
  });

export const automationListQuerySchema = z.object({
  enabled: z.enum(["true", "false"]).optional(),
  triggerKind: z.enum(AUTOMATION_TRIGGER_KINDS).optional(),
});

export type AutomationCreateInput = z.infer<typeof automationCreateSchema>;
export type AutomationUpdateInput = z.infer<typeof automationUpdateSchema>;
export type AutomationListQuery = z.infer<typeof automationListQuerySchema>;
export type AutomationTriggerKind = (typeof AUTOMATION_TRIGGER_KINDS)[number];
export type AutomationRunStatus = (typeof AUTOMATION_RUN_STATUSES)[number];

export interface AutomationDto {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  triggerKind: (typeof AUTOMATION_TRIGGER_KINDS)[number];
  triggerValue: string | null;
  conditions: AutomationCondition[];
  action: string;
  actionPayload: Record<string, JsonValue>;
  cooldownSeconds: number | null;
  lastRunAt: string | null;
  nextRunAt: string | null;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
}
