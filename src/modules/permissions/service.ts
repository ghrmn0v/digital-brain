import "server-only";

import type { Permission } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import type { PermissionDecision } from "@/lib/actions";
import type { JsonValue } from "@/lib/events";
import type {
  PermissionDto,
  PermissionListQuery,
  PermissionUpdateInput,
  PermissionUpsertInput,
} from "@/modules/permissions/contracts";
import { permissionRepository } from "@/modules/permissions/repository";

function toPermissionDto(permission: Permission): PermissionDto {
  return {
    id: permission.id,
    source: permission.source,
    action: permission.action,
    level: permission.level,
    description: permission.description,
    enabled: permission.enabled,
    metadata: (permission.metadata as JsonValue | null) ?? null,
    createdAt: permission.createdAt.toISOString(),
    updatedAt: permission.updatedAt.toISOString(),
  };
}

function assertFound(permission: Permission | null): asserts permission is Permission {
  if (!permission) {
    throw new ApiError(404, "PERMISSION_NOT_FOUND", "Permission not found.");
  }
}

export const permissionService = {
  async list(query: PermissionListQuery) {
    return (await permissionRepository.list(query)).map(toPermissionDto);
  },

  async upsert(input: PermissionUpsertInput) {
    return toPermissionDto(await permissionRepository.upsert(input));
  },

  async update(id: string, input: PermissionUpdateInput) {
    const current = await permissionRepository.findById(id);
    assertFound(current);
    return toPermissionDto(await permissionRepository.update(id, input));
  },

  async remove(id: string) {
    const current = await permissionRepository.findById(id);
    assertFound(current);
    await permissionRepository.delete(id);
  },

  async resolve(source: string, action: string): Promise<PermissionDecision> {
    const policy = await permissionRepository.findPolicy(source, action);
    if (!policy) {
      return {
        level: "ASK_FIRST",
        requiresApproval: true,
        reason: "No explicit permission exists for this action.",
      };
    }
    if (!policy.enabled) {
      return {
        level: "OFF",
        requiresApproval: false,
        reason: "The matching permission entry is disabled.",
      };
    }
    return {
      level: policy.level,
      requiresApproval: policy.level === "ASK_FIRST",
    };
  },
};
