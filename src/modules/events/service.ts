import "server-only";

import { PRODUCT_EVENTS, eventBus } from "@/lib/events/event-bus";
import {
  normalizedEventSchema,
  type JsonValue,
  type NormalizedEvent,
} from "@/lib/events";
import type {
  IntegrationConsumer,
  IntegrationEventDto,
} from "@/modules/events/contracts";
import {
  integrationEventRepository,
  toNormalizedEvent,
} from "@/modules/events/repository";

function toDto(event: {
  eventId: string;
  source: string;
  type: string;
  timestamp: Date;
  payload: unknown;
  metadata: unknown;
  createdAt: Date;
}): IntegrationEventDto {
  return {
    eventId: event.eventId,
    source: event.source,
    type: event.type,
    timestamp: event.timestamp.toISOString(),
    payload: event.payload as Record<string, unknown>,
    metadata: (event.metadata as Record<string, unknown> | null) ?? null,
    createdAt: event.createdAt.toISOString(),
  };
}

export const integrationEventService = {
  async publish(
    input: NormalizedEvent,
    consumers: IntegrationConsumer[],
  ) {
    const event = normalizedEventSchema.parse(input) as NormalizedEvent;
    const result = await integrationEventRepository.createOrGet(event, consumers);

    if (!result.duplicate) {
      await eventBus.emit(PRODUCT_EVENTS.CONNECTOR_EVENT, event);
    }

    return {
      duplicate: result.duplicate,
      event: toDto(result.event),
    };
  },

  async recent(limit = 100) {
    const events = await integrationEventRepository.findRecent(limit);
    return events
      .map((event) => ({
        record: toDto(event),
        normalized: toNormalizedEvent(event),
      }))
      .reverse();
  },

  toDto,
};

export function createNormalizedEvent(options: {
  source: NormalizedEvent["source"];
  type: string;
  payload: Record<string, JsonValue>;
  metadata?: NormalizedEvent["metadata"];
  id?: string;
  timestamp?: string;
}): NormalizedEvent {
  return {
    id: options.id ?? crypto.randomUUID(),
    source: options.source,
    type: options.type,
    timestamp: options.timestamp ?? new Date().toISOString(),
    payload: options.payload,
    metadata: {
      schemaVersion: "1.0",
      ...options.metadata,
    },
  };
}
