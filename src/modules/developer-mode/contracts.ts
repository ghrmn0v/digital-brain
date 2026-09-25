import { z } from "zod";
import type { JsonValue } from "@/lib/events";

export const DEVELOPER_MODE_SETTING_KEY = "product.developer_mode";

export const DEVELOPER_EVENT_TYPES = [
  "developer.bug_detected",
  "developer.explanation",
  "developer.fix_proposed",
  "developer.test_result",
  "developer.review_finding",
  "developer.deploy_status",
] as const;

export type DeveloperEventType = (typeof DEVELOPER_EVENT_TYPES)[number];

export const DEVELOPER_SEVERITIES = [
  "info",
  "warning",
  "error",
  "critical",
] as const;

export type DeveloperSeverity = (typeof DEVELOPER_SEVERITIES)[number];

export const developerModeUpdateSchema = z
  .object({ enabled: z.boolean() })
  .strict();

export const developerDecisionSchema = z
  .object({
    reason: z.string().trim().max(1_000).optional(),
  })
  .strict();

export const developerBugDetectedPayloadSchema = z
  .object({
    repository: z.string().min(1).max(500),
    file: z.string().min(1).max(2_000),
    line: z.number().int().nonnegative().nullable().optional(),
    column: z.number().int().nonnegative().nullable().optional(),
    title: z.string().min(1).max(2_000),
    message: z.string().min(1).max(50_000),
    severity: z.enum(DEVELOPER_SEVERITIES),
    context: z.record(z.string(), z.json()).optional(),
  })
  .strict();

export type DeveloperBugDetectedPayload = z.infer<
  typeof developerBugDetectedPayloadSchema
>;

export interface DeveloperProposalDto {
  id: string;
  eventId: string;
  repository: string;
  file: string;
  line: number | null;
  column: number | null;
  severity: DeveloperSeverity;
  title: string;
  message: string;
  context: Record<string, JsonValue> | null;
  status: "PENDING" | "APPROVED" | "REJECTED";
  decidedBy: string | null;
  decisionReason: string | null;
  decidedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DeveloperInformationDto {
  eventId: string;
  type: DeveloperEventType;
  source: string;
  timestamp: string;
  receivedAt: string;
  payload: Record<string, JsonValue>;
  proposal: DeveloperProposalDto | null;
}
