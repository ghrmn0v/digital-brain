import { z } from "zod";
import { PERMISSION_LEVELS } from "@/lib/actions";
import type { JsonValue } from "@/lib/events";

export const permissionUpsertSchema = z
  .object({
    source: z.string().trim().min(1).max(64),
    action: z
      .string()
      .trim()
      .min(1)
      .max(128)
      .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/),
    level: z.enum(PERMISSION_LEVELS),
    description: z.string().trim().max(1_000).nullable().optional(),
    enabled: z.boolean().default(true),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict();

export const permissionUpdateSchema = z
  .object({
    level: z.enum(PERMISSION_LEVELS).optional(),
    description: z.string().trim().max(1_000).nullable().optional(),
    enabled: z.boolean().optional(),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict()
  .refine((value) => Object.keys(value).length > 0, {
    message: "At least one field must be provided.",
  });

export const permissionListQuerySchema = z.object({
  source: z.string().trim().min(1).max(64).optional(),
  action: z.string().trim().min(1).max(128).optional(),
  enabled: z.enum(["true", "false"]).optional(),
});

export type PermissionUpsertInput = z.infer<typeof permissionUpsertSchema>;
export type PermissionUpdateInput = z.infer<typeof permissionUpdateSchema>;
export type PermissionListQuery = z.infer<typeof permissionListQuerySchema>;

export interface PermissionDto {
  id: string;
  source: string;
  action: string;
  level: (typeof PERMISSION_LEVELS)[number];
  description: string | null;
  enabled: boolean;
  metadata: JsonValue | null;
  createdAt: string;
  updatedAt: string;
}
