export const INTEGRATION_CONSUMERS = ["core_brain", "fly"] as const;
export type IntegrationConsumer = (typeof INTEGRATION_CONSUMERS)[number];

export interface IntegrationEventDto {
  eventId: string;
  source: string;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}
