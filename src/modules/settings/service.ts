import "server-only";

import { Prisma, type AppSetting } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type { SettingDto } from "@/modules/settings/contracts";

function toDto(setting: AppSetting): SettingDto {
  return {
    key: setting.key,
    value: setting.value,
    createdAt: setting.createdAt.toISOString(),
    updatedAt: setting.updatedAt.toISOString(),
  };
}

export const settingsService = {
  async list() {
    return (await prisma.appSetting.findMany({ orderBy: { key: "asc" } })).map(
      toDto,
    );
  },

  async upsert(key: string, value: Prisma.InputJsonValue) {
    return toDto(
      await prisma.appSetting.upsert({
        where: { key },
        create: { key, value },
        update: { value },
      }),
    );
  },

  async remove(key: string) {
    await prisma.appSetting.delete({ where: { key } });
  },
};
