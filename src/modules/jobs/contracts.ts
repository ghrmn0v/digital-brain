import { z } from "zod";
import type { JsonValue } from "@/lib/events";

export const JOB_STATUSES = [
  "seen",
  "saved",
  "ignored",
  "applied",
  "archived",
] as const;

export const JOB_SOURCES = ["linkedin", "manual", "core_brain", "other"] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];
export type JobSource = (typeof JOB_SOURCES)[number];

const optionalDate = z.iso.datetime({ offset: true }).nullable().optional();

export const jobUpsertSchema = z
  .object({
    source: z.enum(JOB_SOURCES).default("linkedin"),
    externalId: z.string().trim().min(1).max(256),
    title: z.string().trim().min(1).max(300),
    company: z.string().trim().min(1).max(200),
    location: z.string().trim().max(300).nullable().optional(),
    employmentType: z.string().trim().max(120).nullable().optional(),
    description: z.string().max(100_000).nullable().optional(),
    url: z.url().max(2_000).nullable().optional(),
    salaryMin: z.number().int().nonnegative().nullable().optional(),
    salaryMax: z.number().int().nonnegative().nullable().optional(),
    salaryCurrency: z.string().trim().min(3).max(3).nullable().optional(),
    skills: z.array(z.string().trim().min(1).max(100)).max(50).optional(),
    relevanceReason: z.string().trim().max(2_000).nullable().optional(),
    status: z.enum(JOB_STATUSES).default("seen"),
    publishedAt: optionalDate,
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.salaryMin !== null &&
      value.salaryMin !== undefined &&
      value.salaryMax !== null &&
      value.salaryMax !== undefined &&
      value.salaryMax < value.salaryMin
    ) {
      context.addIssue({
        code: "custom",
        path: ["salaryMax"],
        message: "salaryMax cannot be lower than salaryMin.",
      });
    }
  });

export const jobUpdateSchema = z
  .object({
    status: z.enum(JOB_STATUSES).optional(),
    relevanceReason: z.string().trim().max(2_000).nullable().optional(),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict()
  .refine((value) => Object.keys(value).length > 0, {
    message: "At least one field must be provided.",
  });

export const jobListQuerySchema = z.object({
  q: z.string().trim().max(100).optional(),
  source: z.enum(JOB_SOURCES).optional(),
  status: z.enum(JOB_STATUSES).optional(),
  company: z.string().trim().max(200).optional(),
});

export const jobReportQuerySchema = z.object({
  since: z.iso.datetime({ offset: true }).optional(),
});

export type JobUpsertInput = z.infer<typeof jobUpsertSchema>;
export type JobUpdateInput = z.infer<typeof jobUpdateSchema>;
export type JobListQuery = z.infer<typeof jobListQuerySchema>;

export interface JobDto {
  id: string;
  source: JobSource;
  externalId: string;
  title: string;
  company: string;
  location: string | null;
  employmentType: string | null;
  description: string | null;
  url: string | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  skills: string[];
  relevanceReason: string | null;
  status: JobStatus;
  publishedAt: string | null;
  firstSeenAt: string;
  lastSeenAt: string;
  appliedAt: string | null;
  archivedAt: string | null;
  metadata: JsonValue | null;
  createdAt: string;
  updatedAt: string;
}
