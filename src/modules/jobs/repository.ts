import "server-only";

import { Prisma, type Job } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type {
  JobListQuery,
  JobUpdateInput,
  JobUpsertInput,
} from "@/modules/jobs/contracts";

function buildWhere(query: JobListQuery): Prisma.JobWhereInput {
  const where: Prisma.JobWhereInput = {};

  if (query.source) where.source = query.source.toUpperCase() as Job["source"];
  if (query.status) where.status = query.status.toUpperCase() as Job["status"];
  if (query.company) where.company = { contains: query.company };
  if (query.q) {
    where.OR = [
      { title: { contains: query.q } },
      { company: { contains: query.q } },
      { location: { contains: query.q } },
    ];
  }

  return where;
}

function toCreateData(input: JobUpsertInput): Prisma.JobCreateInput {
  return {
    source: input.source.toUpperCase() as Job["source"],
    externalId: input.externalId,
    title: input.title,
    company: input.company,
    location: input.location,
    employmentType: input.employmentType,
    description: input.description,
    url: input.url,
    salaryMin: input.salaryMin,
    salaryMax: input.salaryMax,
    salaryCurrency: input.salaryCurrency,
    skills: input.skills as Prisma.InputJsonValue | undefined,
    relevanceReason: input.relevanceReason,
    status: input.status.toUpperCase() as Job["status"],
    publishedAt: input.publishedAt ? new Date(input.publishedAt) : input.publishedAt,
    appliedAt: input.status === "applied" ? new Date() : null,
    archivedAt: input.status === "archived" ? new Date() : null,
    lastSeenAt: new Date(),
    metadata: input.metadata as Prisma.InputJsonValue | undefined,
  };
}

function toIngestionUpdate(input: JobUpsertInput): Prisma.JobUpdateInput {
  const data: Prisma.JobUpdateInput = {
    title: input.title,
    company: input.company,
    lastSeenAt: new Date(),
  };

  if (input.location !== undefined) data.location = input.location;
  if (input.employmentType !== undefined) {
    data.employmentType = input.employmentType;
  }
  if (input.description !== undefined) data.description = input.description;
  if (input.url !== undefined) data.url = input.url;
  if (input.salaryMin !== undefined) data.salaryMin = input.salaryMin;
  if (input.salaryMax !== undefined) data.salaryMax = input.salaryMax;
  if (input.salaryCurrency !== undefined) {
    data.salaryCurrency = input.salaryCurrency;
  }
  if (input.skills !== undefined) {
    data.skills = input.skills as Prisma.InputJsonValue;
  }
  if (input.relevanceReason !== undefined) {
    data.relevanceReason = input.relevanceReason;
  }
  if (input.publishedAt !== undefined) {
    data.publishedAt = input.publishedAt ? new Date(input.publishedAt) : null;
  }
  if (input.metadata !== undefined) {
    data.metadata = input.metadata as Prisma.InputJsonValue;
  }

  return data;
}

function toUpdateData(input: JobUpdateInput): Prisma.JobUpdateInput {
  const data: Prisma.JobUpdateInput = {};
  if (input.relevanceReason !== undefined) {
    data.relevanceReason = input.relevanceReason;
  }
  if (input.metadata !== undefined) {
    data.metadata = input.metadata as Prisma.InputJsonValue;
  }
  if (input.status !== undefined) {
    const status = input.status.toUpperCase() as Job["status"];
    data.status = status;
    if (input.status === "applied") data.appliedAt = new Date();
    if (input.status === "archived") data.archivedAt = new Date();
  }
  return data;
}

export const jobRepository = {
  async list(query: JobListQuery, page: number, limit: number) {
    const where = buildWhere(query);
    const [items, total] = await prisma.$transaction([
      prisma.job.findMany({
        where,
        orderBy: { lastSeenAt: "desc" },
        skip: (page - 1) * limit,
        take: limit,
      }),
      prisma.job.count({ where }),
    ]);
    return { items, total };
  },

  findById(id: string) {
    return prisma.job.findUnique({ where: { id } });
  },

  findByExternalId(source: Job["source"], externalId: string) {
    return prisma.job.findUnique({
      where: { source_externalId: { source, externalId } },
    });
  },

  upsert(input: JobUpsertInput) {
    const source = input.source.toUpperCase() as Job["source"];
    return prisma.job.upsert({
      where: { source_externalId: { source, externalId: input.externalId } },
      create: toCreateData(input),
      update: toIngestionUpdate(input),
    });
  },

  update(id: string, input: JobUpdateInput) {
    return prisma.job.update({ where: { id }, data: toUpdateData(input) });
  },

  archive(id: string) {
    return prisma.job.update({
      where: { id },
      data: { status: "ARCHIVED", archivedAt: new Date() },
    });
  },

  countDiscoveredSince(since: Date) {
    return prisma.job.count({ where: { firstSeenAt: { gte: since } } });
  },

  listDiscoveredSince(since: Date, limit: number) {
    return prisma.job.findMany({
      where: { firstSeenAt: { gte: since } },
      orderBy: { firstSeenAt: "desc" },
      take: limit,
    });
  },
};
