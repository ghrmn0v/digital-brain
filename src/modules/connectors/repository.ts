import "server-only";

import type { Connector } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type { ConnectorHealthStatus } from "@/modules/connectors/contracts";

export const connectorRepository = {
  list() {
    return prisma.connector.findMany({ orderBy: { name: "asc" } });
  },

  findById(id: string) {
    return prisma.connector.findUnique({ where: { id } });
  },

  setEnabled(id: string, enabled: boolean) {
    return prisma.connector.update({ where: { id }, data: { enabled } });
  },

  recordHealth(
    id: string,
    status: ConnectorHealthStatus,
    lastSyncAt?: Date | null,
    message?: string | null,
  ) {
    return prisma.connector.update({
      where: { id },
      data: {
        status: status.toUpperCase() as Connector["status"],
        lastSyncAt,
        lastError: message ?? null,
      },
    });
  },
};
