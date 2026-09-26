import "server-only";

import type { EventDelivery } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import {
  brainUserId,
  toBrainIngestRequest,
} from "@/lib/brain-client/bridge";
import type { IntegrationConsumer } from "@/modules/events/contracts";
import {
  integrationEventRepository,
  toNormalizedEvent,
} from "@/modules/events/repository";

function integrationUrl(consumer: IntegrationConsumer): string | null {
  if (consumer === "core_brain") {
    return process.env.CORE_BRAIN_URL?.trim() || null;
  }
  return process.env.FLY_EVENTS_URL?.trim() || null;
}

function integrationToken(consumer: IntegrationConsumer): string | undefined {
  if (consumer === "core_brain") {
    return process.env.CORE_BRAIN_API_TOKEN?.trim() || undefined;
  }
  return process.env.FLY_API_TOKEN?.trim() || undefined;
}

type IngestOutcome = {
  outcome?: string;
  reason?: string | null;
  /** True when the Brain holds the event: stored now, or already held. */
  accepted: boolean;
};

/** Outcomes that mean the Brain holds the event. */
const _BRAIN_HELD_OUTCOMES = new Set(["accepted", "duplicate"]);

/**
 * Read the Brain's semantic ingest outcome, if it sent one.
 *
 * A body that is absent, not JSON, or not an ingest response is ignored rather
 * than treated as a failure: only the Brain speaks this contract, and a future
 * transport must not start failing deliveries because of a shape it does not
 * know.
 */
async function readIngestOutcome(response: Response): Promise<IngestOutcome | null> {
  if (!response.headers.get("content-type")?.includes("application/json")) {
    return null;
  }
  try {
    const body = (await response.json()) as {
      result?: { outcome?: unknown; reason?: unknown } | null;
    };
    const result = body?.result;
    if (!result || typeof result.outcome !== "string") return null;
    return {
      outcome: result.outcome,
      reason: typeof result.reason === "string" ? result.reason : null,
      accepted: _BRAIN_HELD_OUTCOMES.has(result.outcome),
    };
  } catch {
    return null;
  }
}

async function sendDelivery(
  delivery: EventDelivery & { event: { eventId: string } },
): Promise<void> {
  const url = integrationUrl(delivery.consumer as IntegrationConsumer);
  if (!url) return;

  const eventRecord = await integrationEventRepository.findByEventId(
    delivery.event.eventId,
  );
  if (!eventRecord) {
    await integrationEventRepository.releaseDelivery(
      delivery.id,
      "Integration event record no longer exists.",
      false,
    );
    return;
  }

  const token = integrationToken(delivery.consumer as IntegrationConsumer);
  const timeout = Number(process.env.INTEGRATION_REQUEST_TIMEOUT_MS ?? "5000");

  let body: string;
  if ((delivery.consumer as IntegrationConsumer) === "core_brain") {
    try {
      // Core Brain speaks its own canonical contract: one ApiRequest whose
      // method is `ingest` and whose params carry a Brain
      // NormalizedSourceEvent. Other consumers (Fly) keep Product's own
      // normalized event, which is the interface they already consume.
      body = JSON.stringify(
        toBrainIngestRequest(
          toNormalizedEvent(eventRecord),
          brainUserId(),
          eventRecord.eventId,
        ),
      );
    } catch (error) {
      await integrationEventRepository.releaseDelivery(
        delivery.id,
        (
          error instanceof Error
            ? error.message
            : "Brain contract mapping failed"
        ).slice(0, 500),
        false,
      );
      return;
    }
  } else {
    body = JSON.stringify(toNormalizedEvent(eventRecord));
  }

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "idempotency-key": eventRecord.eventId,
        ...(token ? { authorization: `Bearer ${token}` } : {}),
      },
      body,
      signal: AbortSignal.timeout(Number.isFinite(timeout) ? timeout : 5_000),
      cache: "no-store",
    });

    if (response.ok) {
      // HTTP 200 only means the Brain handled the request. Its ingest contract
      // answers 200 with a *semantic* outcome too, and `rejected` means nothing
      // was stored: a missing required payload field, for example. Recording
      // that as DELIVERED silently loses the event, so the body is inspected
      // before claiming success.
      // Only the Brain speaks the ingest-outcome contract; Fly answers with a
      // behaviour decision, so the check is scoped rather than merely tolerant.
      const outcome =
        (delivery.consumer as IntegrationConsumer) === "core_brain"
          ? await readIngestOutcome(response)
          : null;
      // `accepted` and `duplicate` both mean the Brain holds the event; a
      // duplicate is a successful idempotent delivery, not a failure. Only the
      // outcomes that mean "nothing was stored" fail, and an outcome this
      // version does not recognise also fails rather than being assumed fine —
      // the original bug was claiming success too readily.
      if (outcome && !outcome.accepted) {
        await integrationEventRepository.releaseDelivery(
          delivery.id,
          `Brain did not accept the event: ${outcome.outcome}${
            outcome.reason ? ` (${outcome.reason})` : ""
          }`.slice(0, 500),
          false,
        );
        return;
      }
      await integrationEventRepository.markDelivered(delivery.id);
      return;
    }

    const retryable =
      response.status === 408 || response.status === 429 || response.status >= 500;
    await integrationEventRepository.releaseDelivery(
      delivery.id,
      `Remote consumer returned HTTP ${response.status}.`,
      retryable && delivery.attempts + 1 < 5,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown delivery error";
    await integrationEventRepository.releaseDelivery(
      delivery.id,
      message.slice(0, 500),
      delivery.attempts + 1 < 5,
    );
  }
}

export const eventDeliveryService = {
  async deliverEventId(eventId: string) {
    const event = await integrationEventRepository.findByEventId(eventId);
    if (event) await this.deliverEvent(event.id);
  },

  async deliverEvent(eventDbId: string) {
    const deliveries = await prisma.eventDelivery.findMany({
      where: { eventId: eventDbId },
      include: { event: { select: { eventId: true } } },
    });

    await Promise.all(
      deliveries
        .filter(
          (delivery) =>
            integrationUrl(delivery.consumer as IntegrationConsumer) !== null,
        )
        .map(async (delivery) => {
          const claimed = await integrationEventRepository.claimDelivery(delivery.id);
          if (claimed.count === 0) return;
          await sendDelivery({ ...delivery, attempts: delivery.attempts + 1 });
        }),
    );
  },

  async processPending(limit = 25) {
    const deliveries = await integrationEventRepository.listDueDeliveries(limit);
    for (const delivery of deliveries) {
      if (!integrationUrl(delivery.consumer as IntegrationConsumer)) continue;
      const claimed = await integrationEventRepository.claimDelivery(delivery.id);
      if (claimed.count === 0) continue;
      await sendDelivery({ ...delivery, attempts: delivery.attempts + 1 });
    }
  },
};
