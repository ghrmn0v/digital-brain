import type { Metadata } from "next";
import { ConnectorsManager } from "@/components/connectors-manager";
import { PageHeader } from "@/components/ui";
import { connectorService } from "@/modules/connectors";

export const metadata: Metadata = { title: "Connectors" };

export default async function ConnectorsPage() {
  const records = await connectorService.list();
  const connectors = records.map((connector) => ({
    id: connector.id,
    name: connector.name,
    type: connector.type,
    version: connector.version,
    enabled: connector.enabled,
    status: connector.status,
    lastSyncAt: connector.lastSyncAt,
    lastError: connector.lastError,
    updatedAt: connector.updatedAt,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Integration registry"
        title="Connectors"
        description="Review real seeded connectors, connection health, and recent sync outcomes without exposing credentials or credential values."
      />
      <ConnectorsManager connectors={connectors} />
    </div>
  );
}
