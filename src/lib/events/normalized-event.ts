import { z } from "zod";

export const EVENT_SOURCES = [
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
] as const;

export type EventSource = (typeof EVENT_SOURCES)[number];

export type JsonPrimitive = string | number | boolean | null;

export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];

export interface JsonObject {
  [key: string]: JsonValue;
}

export const normalizedEventSchema = z
  .object({
    id: z.string().min(1).max(128),
    source: z.enum(EVENT_SOURCES),
    type: z.string().min(1).max(128).regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/),
    timestamp: z.iso.datetime({ offset: true }),
    payload: z.record(z.string(), z.json()),
    metadata: z
      .object({
        schemaVersion: z.string().min(1).max(32).optional(),
        connectorVersion: z.string().min(1).max(32).optional(),
        rawId: z.string().min(1).max(256).optional(),
        correlationId: z.string().min(1).max(128).optional(),
      })
      .strict()
      .optional(),
  })
  .strict();

/**
 * Stable boundary contract between connectors, Product, Core Brain, and Fly.
 * Every event must be JSON-serializable and normalized before it is emitted.
 */
export interface NormalizedEvent<TPayload extends JsonObject = JsonObject> {
  id: string;
  source: EventSource;
  type: string;
  timestamp: string;
  payload: TPayload;
  metadata?: {
    schemaVersion?: string;
    connectorVersion?: string;
    rawId?: string;
    correlationId?: string;
  };
}
