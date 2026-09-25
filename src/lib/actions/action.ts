import { z } from "zod";
import type { JsonObject, JsonValue } from "@/lib/events/normalized-event";

export const PERMISSION_LEVELS = [
  "AUTOMATIC",
  "ASK_FIRST",
  "OFF",
] as const;

export type PermissionLevel = (typeof PERMISSION_LEVELS)[number];

export const ACTION_STATUSES = [
  "completed",
  "pending_approval",
  "rejected",
  "failed",
] as const;

export type ActionStatus = (typeof ACTION_STATUSES)[number];

export const actionRequestSchema = z
  .object({
    id: z.string().uuid().optional(),
    source: z.string().min(1).max(64),
    action: z.string().min(1).max(128).regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/),
    payload: z.record(z.string(), z.json()).default({}),
    requestedAt: z.iso.datetime({ offset: true }).optional(),
    correlationId: z.string().min(1).max(128).optional(),
  })
  .strict();

export const actionResponseSchema = z
  .object({
    actionId: z.string().min(1),
    success: z.boolean(),
    status: z.enum(ACTION_STATUSES),
    result: z.json().optional(),
    error: z.string().optional(),
  })
  .strict();

export interface ActionRequest {
  id: string;
  source: string;
  action: string;
  payload: JsonObject;
  requestedAt: string;
  correlationId?: string;
}

export interface ActionResponse {
  actionId: string;
  success: boolean;
  status: ActionStatus;
  result?: JsonValue;
  error?: string;
}

export interface PermissionDecision {
  level: PermissionLevel;
  requiresApproval: boolean;
  reason?: string;
}

export type ActionExecutor = (
  request: ActionRequest,
) => Promise<ActionResponse>;
