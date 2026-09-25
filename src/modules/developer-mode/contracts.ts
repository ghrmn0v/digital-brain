import { z } from "zod";
import type { JsonValue } from "@/lib/events";

export const DEVELOPER_MODE_SETTING_KEY = "product.developer_mode";

/**
 * Mirrors the Core Brain event catalogue exactly.
 *
 * `developer.explanation` is deliberately absent: Core keeps explanations inside
 * the payload of the event they belong to instead of emitting a second event.
 * The deployment event is `developer.deploy_proposed`, because that is what Core
 * emits — Core proposes, Product decides and executes.
 */
export const DEVELOPER_EVENT_TYPES = [
  "developer.bug_detected",
  "developer.fix_proposed",
  "developer.test_result",
  "developer.review_finding",
  "developer.deploy_proposed",
] as const;

export type DeveloperEventType = (typeof DEVELOPER_EVENT_TYPES)[number];

/**
 * Mirrors the Core Brain severity ladder (`info < warning < high < critical`).
 *
 * `error` is retained for events Product itself produced before Core owned the
 * catalogue; Core never emits it, so new code should not generate it.
 */
export const DEVELOPER_SEVERITIES = [
  "info",
  "warning",
  "high",
  "critical",
  "error",
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

/**
 * The Core Brain `developer.bug_detected` payload.
 *
 * Core requires `event_id`, `finding_id`, `confidence` and `correlation_id`
 * alongside the human-readable fields, so those are accepted here: rejecting
 * them would reject every real Brain finding. The descriptive fields Product
 * projects on stay required, which keeps the legacy Product-shaped payload (and
 * the fields Product itself reasons about) valid.
 *
 * The schema stays `.strict()`, so genuine drift is still an error rather than
 * being silently stored.
 */
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
    event_id: z.string().min(1).max(512).optional(),
    finding_id: z.string().min(1).max(512).optional(),
    confidence: z.number().min(0).max(1).optional(),
    correlation_id: z.string().min(1).max(256).optional(),
    check: z.string().min(1).max(200).optional(),
    suggested_fix: z.string().min(1).max(2_000).optional(),
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
