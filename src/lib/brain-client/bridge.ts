/**
 * Translation between Product's internal normalized event and the Core Brain
 * API v1 contract.
 *
 * Product stores one `NormalizedEvent` shape for connectors, Brain and Fly.
 * Core Brain has its own canonical contract, and it is the Brain's contract
 * that wins on the wire:
 *
 * - outbound: `POST /v1/brain` with an `ApiRequest` envelope whose method is
 *   `ingest` and whose `params.event` is a Brain `NormalizedSourceEvent`;
 * - inbound: a Brain `BrainEvent`.
 *
 * The Brain rejects unknown fields, so nothing is forwarded blindly: Product's
 * `metadata` is dropped except for a correlation id, which becomes the Brain's
 * top-level `correlation_id`.
 *
 * The Brain requires a `user_id` on every event. Product is local-first and
 * single-user, so the owner is configuration (`CORE_BRAIN_USER_ID`) rather than
 * an invented per-event value. A missing value fails the delivery loudly
 * instead of attributing somebody's data to the wrong identity.
 */

import type {
  ApiRequest,
  BrainEvent,
  NormalizedSourceEvent,
  Source,
} from "@/lib/brain-client";
import type { NormalizedEvent } from "@/lib/events";

/** Brain event types are `source.<provider>.<action>` with underscore actions. */
const CANONICAL_TYPE_RE = /^source\.[a-z0-9_]+(\.[a-z0-9_]+)+$/;

export class BrainContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BrainContractError";
  }
}

/** Product providers that are not valid Brain source providers. */
const PROVIDER_ALIASES: Record<string, string> = {
  other: "product",
};

export function brainUserId(): string {
  const value = process.env.CORE_BRAIN_USER_ID?.trim();
  if (!value) {
    throw new BrainContractError(
      "CORE_BRAIN_USER_ID is required to deliver events to Core Brain; " +
        "the Brain isolates every event by user.",
    );
  }
  return value;
}

/**
 * Map a Product event type to the Brain's canonical form.
 *
 * `job.discovered` + provider `linkedin` becomes
 * `source.linkedin.job_discovered`, which is what the Brain's mapping registry
 * understands. A type that already is canonical is kept as is.
 */
export function canonicalBrainEventType(
  eventType: string,
  provider: string,
): string {
  const trimmed = eventType.trim();
  if (CANONICAL_TYPE_RE.test(trimmed)) return trimmed;
  const source = PROVIDER_ALIASES[provider] ?? provider;
  const action = trimmed
    .replace(/^source\./, "")
    .replace(/[.\-]+/g, "_")
    .replace(/[^a-z0-9_]/gi, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
  if (!source || !action) {
    throw new BrainContractError(
      `cannot map event type ${JSON.stringify(eventType)} with provider ` +
        `${JSON.stringify(provider)} onto the Core Brain contract`,
    );
  }
  return `source.${source}.${action}`;
}

/** Product event -> Brain `NormalizedSourceEvent`. */
export function toBrainSourceEvent(
  event: NormalizedEvent,
  userId: string,
): NormalizedSourceEvent {
  const correlationId = event.metadata?.correlationId ?? null;
  const source: Source = { provider: PROVIDER_ALIASES[event.source] ?? event.source };
  return {
    id: event.id,
    type: canonicalBrainEventType(event.type, event.source),
    timestamp: event.timestamp,
    occurred_at: event.timestamp,
    user_id: userId,
    source,
    payload: event.payload,
    ...(correlationId ? { correlation_id: correlationId } : {}),
  };
}

/** A Product event as the Brain `ingest` request envelope. */
export function toBrainIngestRequest(
  event: NormalizedEvent,
  userId: string,
  requestId: string,
): ApiRequest<{ event: NormalizedSourceEvent }> {
  return {
    id: requestId,
    method: "ingest",
    version: "v1",
    params: { event: toBrainSourceEvent(event, userId) },
  };
}

type ProductEventSource = NormalizedEvent["source"];

const BRAIN_SOURCES: ReadonlySet<ProductEventSource> = new Set([
  "linkedin",
  "calendar",
  "whatsapp",
  "telegram",
  "browser",
  "system",
  "core_brain",
  "fly",
  "manual",
  "other",
]);

/**
 * Core labels its own provenance `core` (`Source(provider="core")` in the
 * emitter). Product stores that as `core_brain`, which is also the value its own
 * developer-mode projection keys on, so a real Brain event has to land there
 * rather than in `other`.
 */
const BRAIN_PROVIDER_TO_PRODUCT: Record<string, ProductEventSource> = {
  core: "core_brain",
};

/** Map a Brain provider onto the closest Product event source. */
function toProductSource(provider: string): ProductEventSource {
  const alias = BRAIN_PROVIDER_TO_PRODUCT[provider];
  if (alias !== undefined) return alias;
  return BRAIN_SOURCES.has(provider as ProductEventSource)
    ? (provider as ProductEventSource)
    : "other";
}

function isBrainEvent(value: unknown): value is BrainEvent {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.id === "string" &&
    typeof record.type === "string" &&
    typeof record.user_id === "string" &&
    typeof record.timestamp === "string" &&
    typeof record.source === "object" &&
    record.source !== null &&
    typeof (record.source as Record<string, unknown>).provider === "string"
  );
}

/**
 * Accept either a canonical Brain `BrainEvent` or the legacy Product
 * `NormalizedEvent`, and return the Product shape the rest of Product stores.
 *
 * The legacy branch keeps existing callers (and the smoke test) working while
 * the canonical shape is the primary contract.
 */
export function toProductEvent(value: unknown): NormalizedEvent {
  if (isBrainEvent(value)) {
    const brainEvent = value;
    const correlationId =
      typeof brainEvent.payload?.["correlation_id"] === "string"
        ? brainEvent.payload["correlation_id"]
        : undefined;
    const provider = brainEvent.source.provider;
    const metadata: Record<string, string> = { schemaVersion: "1.0" };
    if (correlationId) metadata.correlationId = correlationId;
    return {
      id: brainEvent.id,
      source: toProductSource(provider),
      type: brainEvent.type,
      timestamp: brainEvent.timestamp,
      payload: (brainEvent.payload ?? {}) as Record<string, never>,
      metadata,
    };
  }
  throw new BrainContractError(
    "event is neither a Core Brain BrainEvent nor a Product normalized event",
  );
}
