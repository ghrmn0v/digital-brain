import "server-only";

import type { Job } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import type { JsonValue } from "@/lib/events";
import type {
  JobDto,
  JobListQuery,
  JobSource,
  JobStatus,
  JobUpdateInput,
  JobUpsertInput,
} from "@/modules/jobs/contracts";
import { jobRepository } from "@/modules/jobs/repository";

function toJobDto(job: Job): JobDto {
  const skills = Array.isArray(job.skills)
    ? job.skills.filter((skill): skill is string => typeof skill === "string")
    : [];

  return {
    id: job.id,
    source: job.source.toLowerCase() as JobSource,
    externalId: job.externalId,
    title: job.title,
    company: job.company,
    location: job.location,
    employmentType: job.employmentType,
    description: job.description,
    url: job.url,
    salaryMin: job.salaryMin,
    salaryMax: job.salaryMax,
    salaryCurrency: job.salaryCurrency,
    skills,
    relevanceReason: job.relevanceReason,
    status: job.status.toLowerCase() as JobStatus,
    publishedAt: job.publishedAt?.toISOString() ?? null,
    firstSeenAt: job.firstSeenAt.toISOString(),
    lastSeenAt: job.lastSeenAt.toISOString(),
    appliedAt: job.appliedAt?.toISOString() ?? null,
    archivedAt: job.archivedAt?.toISOString() ?? null,
    metadata: (job.metadata as JsonValue | null) ?? null,
    createdAt: job.createdAt.toISOString(),
    updatedAt: job.updatedAt.toISOString(),
  };
}

function assertFound(job: Job | null): asserts job is Job {
  if (!job) throw new ApiError(404, "JOB_NOT_FOUND", "Job not found.");
}

export const jobService = {
  async list(query: JobListQuery, page: number, limit: number) {
    const { items, total } = await jobRepository.list(query, page, limit);
    return {
      items: items.map(toJobDto),
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    };
  },

  async get(id: string) {
    const job = await jobRepository.findById(id);
    assertFound(job);
    return toJobDto(job);
  },

  async upsert(input: JobUpsertInput) {
    return toJobDto(await jobRepository.upsert(input));
  },

  async ingest(input: JobUpsertInput) {
    const source = input.source.toUpperCase() as Job["source"];
    const existing = await jobRepository.findByExternalId(
      source,
      input.externalId,
    );
    const job = toJobDto(await jobRepository.upsert(input));
    return { job, created: existing === null };
  },

  async update(id: string, input: JobUpdateInput) {
    const current = await jobRepository.findById(id);
    assertFound(current);
    return toJobDto(await jobRepository.update(id, input));
  },

  async archive(id: string) {
    const current = await jobRepository.findById(id);
    assertFound(current);
    return toJobDto(await jobRepository.archive(id));
  },

  async report(since?: Date) {
    const from = since ?? new Date(Date.now() - 24 * 60 * 60 * 1000);
    const [total, items] = await Promise.all([
      jobRepository.countDiscoveredSince(from),
      jobRepository.listDiscoveredSince(from, 100),
    ]);
    return {
      period: { from: from.toISOString(), to: new Date().toISOString() },
      total,
      jobs: items.map(toJobDto),
    };
  },
};
