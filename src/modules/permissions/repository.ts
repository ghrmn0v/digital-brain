import "server-only";

import { Prisma } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type {
  PermissionListQuery,
  PermissionUpdateInput,
  PermissionUpsertInput,
} from "@/modules/permissions/contracts";

export const permissionRepository = {
  async list(query: PermissionListQuery) {
    const where: Prisma.PermissionWhereInput = {};
    if (query.source) where.source = query.source;
    if (query.action) where.action = { contains: query.action };
    if (query.enabled) where.enabled = query.enabled === "true";

    return prisma.permission.findMany({
      where,
      orderBy: [{ source: "asc" }, { action: "asc" }],
    });
  },

  findById(id: string) {
    return prisma.permission.findUnique({ where: { id } });
  },

  findPolicy(source: string, action: string) {
    return prisma.permission.findUnique({
      where: { source_action: { source, action } },
    });
  },

  upsert(input: PermissionUpsertInput) {
    return prisma.permission.upsert({
      where: { source_action: { source: input.source, action: input.action } },
      create: {
        source: input.source,
        action: input.action,
        level: input.level,
        description: input.description,
        enabled: input.enabled,
        metadata: input.metadata as Prisma.InputJsonValue | undefined,
      },
      update: {
        level: input.level,
        description: input.description,
        enabled: input.enabled,
        metadata: input.metadata as Prisma.InputJsonValue | undefined,
      },
    });
  },

  update(id: string, input: PermissionUpdateInput) {
    const data: Prisma.PermissionUpdateInput = {};
    if (input.level !== undefined) data.level = input.level;
    if (input.description !== undefined) data.description = input.description;
    if (input.enabled !== undefined) data.enabled = input.enabled;
    if (input.metadata !== undefined) {
      data.metadata = input.metadata as Prisma.InputJsonValue;
    }
    return prisma.permission.update({ where: { id }, data });
  },

  delete(id: string) {
    return prisma.permission.delete({ where: { id } });
  },
};
