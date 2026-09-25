import "server-only";

import type { Connector } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import type { ConnectorDto, ConnectorHealthStatus } from "@/modules/connectors/contracts";
import { LinkedInConnector } from "@/modules/connectors/linkedin";
import { connectorRepository } from "@/modules/connectors/repository";

function toDto(connector: Connector): ConnectorDto {
  return {
    id: connector.id,
    name: connector.name,
    type: connector.type,
    version: connector.version,
    enabled: connector.enabled,
    status: connector.status.toLowerCase() as ConnectorHealthStatus,
    hasCredentialReference: connector.credentialsRef !== null,
    lastSyncAt: connector.lastSyncAt?.toISOString() ?? null,
    lastError: connector.lastError,
    metadata: (connector.metadata as Record<string, unknown> | null) ?? null,
    createdAt: connector.createdAt.toISOString(),
    updatedAt: connector.updatedAt.toISOString(),
  };
}

function assertFound(connector: Connector | null): asserts connector is Connector {
  if (!connector) {
    throw new ApiError(404, "CONNECTOR_NOT_FOUND", "Connector not found.");
  }
}

const globalForConnectors = globalThis as unknown as {
  linkedInConnector?: LinkedInConnector;
};

export const linkedInConnector =
  globalForConnectors.linkedInConnector ?? new LinkedInConnector();

if (process.env.NODE_ENV !== "production") {
  globalForConnectors.linkedInConnector = linkedInConnector;
}

export const connectorService = {
  async list() {
    return (await connectorRepository.list()).map(toDto);
  },

  async get(id: string) {
    const connector = await connectorRepository.findById(id);
    assertFound(connector);
    return toDto(connector);
  },

  async setEnabled(id: string, enabled: boolean) {
    const connector = await connectorRepository.findById(id);
    assertFound(connector);
    return toDto(await connectorRepository.setEnabled(id, enabled));
  },

  async recordHealth(
    id: string,
    status: ConnectorHealthStatus,
    lastSyncAt?: Date | null,
    message?: string | null,
  ) {
    const connector = await connectorRepository.findById(id);
    assertFound(connector);
    return toDto(
      await connectorRepository.recordHealth(id, status, lastSyncAt, message),
    );
  },
};
