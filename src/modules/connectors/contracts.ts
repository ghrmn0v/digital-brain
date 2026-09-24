import { z } from "zod";

export const CONNECTOR_HEALTH_STATUSES = [
  "healthy",
  "degraded",
  "disconnected",
  "error",
] as const;

export type ConnectorHealthStatus = (typeof CONNECTOR_HEALTH_STATUSES)[number];

export const connectorUpdateSchema = z
  .object({ enabled: z.boolean() })
  .strict();

export const connectorHealthSchema = z
  .object({
    status: z.enum(CONNECTOR_HEALTH_STATUSES),
    lastSyncAt: z.iso.datetime({ offset: true }).nullable().optional(),
    message: z.string().trim().max(1_000).nullable().optional(),
  })
  .strict();

export const linkedInJobsIngestionSchema = z
  .object({
    jobs: z
      .array(
        z
          .object({
            externalId: z.string().trim().min(1).max(256),
            title: z.string().trim().min(1).max(300),
            company: z.string().trim().min(1).max(200),
            location: z.string().trim().max(300).nullable().optional(),
            employmentType: z.string().trim().max(120).nullable().optional(),
            description: z.string().max(100_000).nullable().optional(),
            url: z.url().max(2_000).nullable().optional(),
            salaryMin: z.number().int().nonnegative().nullable().optional(),
            salaryMax: z.number().int().nonnegative().nullable().optional(),
            salaryCurrency: z
              .string()
              .trim()
              .min(3)
              .max(3)
              .nullable()
              .optional(),
            skills: z.array(z.string().trim().min(1).max(100)).max(50).optional(),
            publishedAt: z.iso.datetime({ offset: true }).nullable().optional(),
            metadata: z.record(z.string(), z.json()).optional(),
          })
          .strict(),
      )
      .min(1)
      .max(100),
  })
  .strict();

export interface ConnectorDto {
  id: string;
  name: string;
  type: string;
  version: string;
  enabled: boolean;
  status: ConnectorHealthStatus;
  hasCredentialReference: boolean;
  lastSyncAt: string | null;
  lastError: string | null;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}
