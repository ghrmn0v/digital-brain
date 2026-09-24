import { z } from "zod";

export const settingUpsertSchema = z
  .object({
    key: z
      .string()
      .trim()
      .min(1)
      .max(128)
      .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/),
    value: z.json(),
  })
  .strict();

export interface SettingDto {
  key: string;
  value: unknown;
  createdAt: string;
  updatedAt: string;
}
