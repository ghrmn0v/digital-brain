import "server-only";

import { randomUUID } from "node:crypto";
import { Prisma, type IntegrationEvent } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type { JsonValue, NormalizedEvent } from "@/lib/events";
import type { IntegrationConsumer } from "@/modules/events/contracts";

export const integrationEventRepository = {
  async createOrGet(
    event: NormalizedEvent,
    consumers: IntegrationConsumer[],
  ) {
    return prisma.$transaction(async (transaction) => {
      const existing = await transaction.integrationEvent.findUnique({
        where: { eventId: event.id },
      });

      if (existing) {
        for (const consumer of consumers) {
          await transaction.eventDelivery.upsert({
            where: {
              eventId_consumer: { eventId: existing.id, consumer },
            },
            update: {},
            create: { eventId: existing.id, consumer },
          });
        }
        return { event: existing, duplicate: true };
      }

      const created = await transaction.integrationEvent.create({
        data: {
          eventId: event.id,
          source: event.source,
          type: event.type,
          timestamp: new Date(event.timestamp),
          payload: event.payload as Prisma.InputJsonValue,
          metadata: event.metadata as Prisma.InputJsonValue | undefined,
          deliveries: {
            create: consumers.map((consumer) => ({ consumer })),
          },
        },
      });
      return { event: created, duplicate: false };
    });
  },

  findByEventId(eventId: string) {
    return prisma.integrationEvent.findUnique({ where: { eventId } });
  },

  findRecent(limit: number) {
    return prisma.integrationEvent.findMany({
      orderBy: { createdAt: "desc" },
      take: limit,
    });
  },

  listDeliveries(eventDbId: string) {
    return prisma.eventDelivery.findMany({
      where: { eventId: eventDbId },
      orderBy: { consumer: "asc" },
    });
  },

  listDueDeliveries(limit: number) {
    return prisma.eventDelivery.findMany({
      where: {
        status: { in: ["PENDING", "FAILED"] },
        attempts: { lt: 5 },
        nextAttemptAt: { lte: new Date() },
      },
      include: { event: true },
      orderBy: { nextAttemptAt: "asc" },
      take: limit,
    });
  },

  claimDelivery(id: string) {
    return prisma.eventDelivery.updateMany({
      where: {
        id,
        status: { in: ["PENDING", "FAILED"] },
        attempts: { lt: 5 },
      },
      data: {
        status: "DELIVERING",
        attempts: { increment: 1 },
      },
    });
  },

  markDelivered(id: string) {
    return prisma.eventDelivery.update({
      where: { id },
      data: { status: "DELIVERED", deliveredAt: new Date(), lastError: null },
    });
  },

  releaseDelivery(id: string, lastError: string, retry: boolean) {
    return prisma.eventDelivery.update({
      where: { id },
      data: {
        status: retry ? "PENDING" : "FAILED",
        lastError,
        nextAttemptAt: new Date(Date.now() + 5_000),
      },
    });
  },
};

export function toNormalizedEvent(event: IntegrationEvent): NormalizedEvent {
  return {
    id: event.eventId,
    source: event.source as NormalizedEvent["source"],
    type: event.type,
    timestamp: event.timestamp.toISOString(),
    payload: event.payload as JsonValue as Record<string, JsonValue>,
    metadata: (event.metadata as Record<string, JsonValue> | null) ?? undefined,
  };
}

export function createEventId(): string {
  return randomUUID();
}
