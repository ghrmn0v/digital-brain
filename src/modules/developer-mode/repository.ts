import "server-only";

import { Prisma, type DeveloperProposal } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import {
  DEVELOPER_EVENT_TYPES,
  DEVELOPER_MODE_SETTING_KEY,
} from "@/modules/developer-mode/contracts";

export const developerModeRepository = {
  async isEnabled(): Promise<boolean> {
    const setting = await prisma.appSetting.findUnique({
      where: { key: DEVELOPER_MODE_SETTING_KEY },
    });
    return setting?.value === true;
  },

  async setEnabled(enabled: boolean) {
    return prisma.appSetting.upsert({
      where: { key: DEVELOPER_MODE_SETTING_KEY },
      create: { key: DEVELOPER_MODE_SETTING_KEY, value: enabled },
      update: { value: enabled },
    });
  },

  findEvent(eventId: string) {
    return prisma.integrationEvent.findUnique({ where: { eventId } });
  },

  upsertProposal(eventDbId: string) {
    return prisma.developerProposal.upsert({
      where: { eventId: eventDbId },
      create: { eventId: eventDbId },
      update: {},
    });
  },

  listInformation(limit: number) {
    return prisma.integrationEvent.findMany({
      where: { type: { in: [...DEVELOPER_EVENT_TYPES] } },
      include: { developerProposal: true },
      orderBy: { createdAt: "desc" },
      take: limit,
    });
  },

  listProposals(limit: number) {
    return prisma.developerProposal.findMany({
      include: { event: true },
      orderBy: { createdAt: "desc" },
      take: limit,
    });
  },

  findProposal(id: string) {
    return prisma.developerProposal.findUnique({
      where: { id },
      include: { event: true },
    });
  },

  decide(
    id: string,
    status: Exclude<DeveloperProposal["status"], "PENDING">,
    decidedBy: string,
    reason?: string,
  ) {
    return prisma.developerProposal.updateMany({
      where: { id, status: "PENDING" },
      data: {
        status,
        decidedBy,
        decisionReason: reason ?? null,
        decidedAt: new Date(),
      },
    });
  },
};

export type DeveloperProposalWithEvent = Prisma.DeveloperProposalGetPayload<{
  include: { event: true };
}>;
