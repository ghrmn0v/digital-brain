import type { NormalizedEvent } from "@/lib/events";

export type ConnectorCredentials = Readonly<Record<string, unknown>>;

export interface ConnectorConfig {
  id: string;
  name: string;
  enabled: boolean;
  /**
   * In-memory credentials for authentication only. Persist a secret-vault
   * reference in Connector.credentialsRef; never store raw secrets in SQLite.
   */
  credentialsRecord?: ConnectorCredentials;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "disconnected" | "error";
  lastSyncAt?: Date;
  message?: string;
}

export abstract class BaseConnector {
  abstract readonly id: string;
  abstract readonly name: string;
  abstract readonly version: string;

  abstract authenticate(config: ConnectorConfig): Promise<boolean>;
  abstract connect(): Promise<boolean>;
  abstract disconnect(): Promise<boolean>;
  abstract healthCheck(): Promise<HealthStatus>;

  abstract normalize(
    rawData: unknown,
    eventType: string,
  ): NormalizedEvent;
}
