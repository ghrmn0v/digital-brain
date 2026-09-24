import { z } from "zod";
import { ACTION_STATUSES } from "@/lib/actions";
import type { JsonValue } from "@/lib/events";

export const actionExecutionListQuerySchema = z.object({
  status: z.enum(ACTION_STATUSES).optional(),
  source: z.string().trim().min(1).max(64).optional(),
  action: z.string().trim().min(1).max(128).optional(),
});

export const actionDecisionSchema = z
  .object({
    reason: z.string().trim().max(1_000).optional(),
  })
  .strict();

export type ActionExecutionListQuery = z.infer<
  typeof actionExecutionListQuerySchema
>;

export interface ActionExecutionDto {
  id: string;
  source: string;
  action: string;
  payload: Record<string, unknown>;
  status: (typeof ACTION_STATUSES)[number];
  permissionLevel: string | null;
  idempotencyKey: string | null;
  correlationId: string | null;
  result: JsonValue | null;
  error: string | null;
  decidedBy: string | null;
  decisionReason: string | null;
  attempts: number;
  requestedAt: string;
  decidedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  updatedAt: string;
}
