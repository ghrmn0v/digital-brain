/**
 * Transport-agnostic request/response plumbing shared by the HTTP and
 * WebSocket clients.
 *
 * Nothing here performs I/O. The invariants enforced here are the ones both
 * transports must honour:
 *
 * - one monotonic request id per client instance;
 * - the envelope invariants of `ApiResponse` (a `BadRequest` HTML body or a
 *   truncated frame is a transport error, never a silent `ok=false`);
 * - ownership params get the configured `user_id` injected, and a conflicting
 *   value is rejected locally;
 * - events are deduplicated by `BrainEvent.id` and filtered by `user_id`
 *   before any handler sees them.
 */

import type {
  ApiError,
  ApiRequest,
  ApiResponse,
  BrainEvent,
  EventEnvelope,
  JsonObject,
  MethodParams,
  ResponseEnvelope,
  StreamFrame,
  ApiMethod,
} from "./contract.ts";
import { API_VERSION, methodHasUserIdParam } from "./contract.ts";
import { BrainApiError, BrainContractError, BrainTransportError } from "./errors.ts";

export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;
export const DEFAULT_CONNECT_TIMEOUT_MS = 10_000;
export const DEFAULT_DEDUPE_CAPACITY = 1024;
export const MAX_IDENTITY_LENGTH = 512;

export interface RequestOptions {
  readonly correlationId?: string | null;
  readonly timeoutMs?: number | null;
}

interface ParsedEnvelope {
  readonly id: string;
  readonly method: string | null;
  readonly ok: boolean;
  readonly result: unknown;
  readonly error: ApiError | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asApiError(value: unknown): ApiError | null {
  if (!isRecord(value)) {
    return null;
  }
  const code = value["code"];
  const message = value["message"];
  if (typeof code !== "string" || typeof message !== "string") {
    return null;
  }
  const source = value["source"];
  const details = value["details"];
  return {
    code,
    message,
    source: typeof source === "string" ? source : null,
    details: isRecord(details) ? (details as JsonObject) : undefined,
  };
}

function parseApiResponse(value: unknown, context: string): ParsedEnvelope {
  if (!isRecord(value)) {
    throw new BrainTransportError(
      `${context}: response body is not a JSON object`,
      { details: { received: typeof value } },
    );
  }
  const id = value["id"];
  const ok = value["ok"];
  if (typeof id !== "string" || id === "") {
    throw new BrainTransportError(`${context}: response is missing a string id`);
  }
  if (typeof ok !== "boolean") {
    throw new BrainTransportError(`${context}: response is missing a boolean ok`);
  }
  const method = value["method"];
  const error = asApiError(value["error"]);
  if (ok) {
    if (error !== null) {
      throw new BrainTransportError(
        `${context}: ok response must not carry an error`,
        { code: error.code, details: { requestId: id } },
      );
    }
  } else if (error === null) {
    throw new BrainTransportError(`${context}: failed response is missing an error`, {
      details: { requestId: id },
    });
  }
  return {
    id,
    method: typeof method === "string" ? method : null,
    ok,
    result: value["result"] ?? null,
    error,
  };
}

/** Structural check for a `kind`-tagged stream frame. */
export function parseStreamFrame(value: unknown): StreamFrame | null {
  if (!isRecord(value)) {
    return null;
  }
  const kind = value["kind"];
  if (kind !== "response" && kind !== "event") {
    return null;
  }
  const payload = value["payload"];
  if (!isRecord(payload)) {
    return null;
  }
  if (kind === "response") {
    if (typeof payload["id"] !== "string" || typeof payload["ok"] !== "boolean") {
      return null;
    }
    return { kind: "response", payload: payload as unknown as ApiResponse };
  }
  const event = payload;
  if (
    typeof event["id"] !== "string" ||
    typeof event["type"] !== "string" ||
    typeof event["user_id"] !== "string"
  ) {
    return null;
  }
  return { kind: "event", payload: event as unknown as BrainEvent };
}

export function isResponseEnvelope(frame: StreamFrame): frame is ResponseEnvelope {
  return frame.kind === "response";
}

export function isEventEnvelope(frame: StreamFrame): frame is EventEnvelope {
  return frame.kind === "event";
}

export function correlationIdOf(event: BrainEvent): string | null {
  const payload = event.payload;
  if (payload === undefined) {
    return null;
  }
  const value = payload["correlation_id"];
  return typeof value === "string" && value !== "" ? value : null;
}

/** Rejects identities the Core WebSocket adapter would refuse (1008). */
export function assertValidUserId(userId: string): string {
  if (typeof userId !== "string" || userId.length === 0) {
    throw new BrainContractError("user_id must be a non-empty string", "identity");
  }
  if (userId.length > MAX_IDENTITY_LENGTH) {
    throw new BrainContractError(
      `user_id must be at most ${MAX_IDENTITY_LENGTH} characters`,
      "identity",
    );
  }
  if (userId.trim() !== userId) {
    throw new BrainContractError("user_id must not have leading or trailing whitespace", "identity");
  }
  for (let index = 0; index < userId.length; index += 1) {
    const code = userId.charCodeAt(index);
    if (code <= 0x20 || code === 0x7f) {
      throw new BrainContractError("user_id must not contain control characters", "identity");
    }
    if (code >= 0xd800 && code <= 0xdfff) {
      throw new BrainContractError("user_id must not contain surrogate code points", "identity");
    }
  }
  return userId;
}

export function buildUserIdQuery(userId: string): string {
  return `?user_id=${encodeURIComponent(userId)}`;
}

export function joinUrl(baseUrl: string, path: string): string {
  const base = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

export type EventHandler = (event: BrainEvent) => void;

export interface EventDispatcherOptions {
  readonly userId: string;
  readonly dedupeCapacity?: number;
  readonly onIgnoredFrame?: (raw: string) => void;
}

export interface EventDispatcherStats {
  framesDecoded: number;
  framesIgnored: number;
  eventsReceived: number;
  eventsDelivered: number;
  eventsDroppedDuplicate: number;
  eventsDroppedForeignUser: number;
}

/**
 * Consumer-side event rules from `docs/event-delivery.md`: at-most-once
 * delivery, deduplication by `BrainEvent.id`, per-user filtering, FIFO order
 * and a bounded deduplication window.
 */
export class EventDispatcher {
  private readonly userId: string;
  private readonly capacity: number;
  private readonly handlers = new Set<EventHandler>();
  private readonly seen: Set<string> = new Set<string>();
  private readonly onIgnoredFrame: ((raw: string) => void) | undefined;
  private readonly counters: EventDispatcherStats = {
    framesDecoded: 0,
    framesIgnored: 0,
    eventsReceived: 0,
    eventsDelivered: 0,
    eventsDroppedDuplicate: 0,
    eventsDroppedForeignUser: 0,
  };

  constructor(options: EventDispatcherOptions) {
    this.userId = options.userId;
    this.capacity = options.dedupeCapacity ?? DEFAULT_DEDUPE_CAPACITY;
    this.onIgnoredFrame = options.onIgnoredFrame;
  }

  get stats(): Readonly<EventDispatcherStats> {
    return { ...this.counters };
  }

  get handlerCount(): number {
    return this.handlers.size;
  }

  subscribe(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  /** Returns the decoded frame, or `null` when the payload is not a frame. */
  accept(raw: string): StreamFrame | null {
    this.counters.framesDecoded += 1;
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return this.ignore(raw);
    }
    const frame = parseStreamFrame(parsed);
    if (frame === null) {
      return this.ignore(raw);
    }
    if (isEventEnvelope(frame)) {
      this.deliver(frame.payload);
    }
    return frame;
  }

  private ignore(raw: string): null {
    this.counters.framesIgnored += 1;
    if (this.onIgnoredFrame !== undefined) {
      this.onIgnoredFrame(raw);
    }
    return null;
  }

  private deliver(event: BrainEvent): void {
    this.counters.eventsReceived += 1;
    if (this.seen.has(event.id)) {
      this.counters.eventsDroppedDuplicate += 1;
      return;
    }
    if (event.user_id !== this.userId) {
      this.counters.eventsDroppedForeignUser += 1;
      return;
    }
    this.remember(event.id);
    for (const handler of [...this.handlers]) {
      this.counters.eventsDelivered += 1;
      handler(event);
    }
  }

  private remember(id: string): void {
    this.seen.add(id);
    if (this.seen.size > this.capacity) {
      const oldest = this.seen.values().next();
      if (oldest.done !== true) {
        this.seen.delete(oldest.value);
      }
    }
  }
}

export interface PreparedRequest {
  readonly envelope: ApiRequest<unknown>;
  readonly id: string;
}

/**
 * Builds one request envelope: identity injection, id minting and the local
 * preconditions shared by both transports.
 */
export class RequestBuilder {
  private readonly userId: string | null;
  private readonly idPrefix: string;
  private counter = 0;

  constructor(options: { readonly userId?: string | null; readonly idPrefix?: string | undefined }) {
    this.userId = options.userId ?? null;
    this.idPrefix = options.idPrefix ?? "brain";
  }

  nextId(): string {
    this.counter += 1;
    return `${this.idPrefix}-${this.counter}`;
  }

  prepare<M extends ApiMethod>(
    method: M,
    params: MethodParams<M> | Record<string, unknown> | undefined,
    options: RequestOptions = {},
    context: { readonly enforceIdentity?: boolean } = {},
  ): PreparedRequest {
    const enforceIdentity = context.enforceIdentity ?? false;
    const id = this.nextId();
    const merged = this.mergeUserId(method, params, enforceIdentity, id);
    if (merged === null) {
      const envelope: ApiRequest<unknown> = { id, method, version: API_VERSION };
      if (options.correlationId !== undefined && options.correlationId !== null) {
        return { id, envelope: this.withCorrelation(envelope, options.correlationId) };
      }
      return { id, envelope };
    }
    const envelope: ApiRequest<unknown> = {
      id,
      method,
      version: API_VERSION,
      params: merged,
    };
    if (options.correlationId !== undefined && options.correlationId !== null) {
      return { id, envelope: this.withCorrelation(envelope, options.correlationId) };
    }
    return { id, envelope };
  }

  private withCorrelation(
    envelope: ApiRequest<unknown>,
    correlationId: string,
  ): ApiRequest<unknown> {
    const params = isRecord(envelope.params) ? { ...envelope.params } : {};
    if (envelope.method === "ingest" || envelope.method === "record_feedback") {
      const nested = isRecord(params["event"])
        ? { ...(params["event"] as JsonObject) }
        : isRecord(params["feedback"])
          ? { ...(params["feedback"] as JsonObject) }
          : null;
      if (nested !== null) {
        const key = envelope.method === "ingest" ? "event" : "feedback";
        params[key] = { ...nested, correlation_id: correlationId };
        return { ...envelope, params };
      }
    }
    return { ...envelope, params: { ...params, correlation_id: correlationId } };
  }

  private mergeUserId(
    method: string,
    params: unknown,
    enforceIdentity: boolean,
    requestId: string,
  ): Record<string, unknown> | null {
    const base: Record<string, unknown> = isRecord(params) ? { ...params } : {};
    if (!methodHasUserIdParam(method)) {
      return base;
    }
    const supplied = base["user_id"];
    if (this.userId === null) {
      return base;
    }
    if (typeof supplied === "string" && supplied !== "") {
      if (supplied !== this.userId) {
        throw new BrainContractError(
          `params.user_id "${supplied}" conflicts with the client identity "${this.userId}"`,
          enforceIdentity ? "identity" : "contract",
          { method, requestId },
        );
      }
      return base;
    }
    base["user_id"] = this.userId;
    return base;
  }
}

export function unwrapResponse(
  raw: unknown,
  method: string,
  requestId: string,
  context: string,
): unknown {
  const parsed = parseApiResponse(raw, context);
  if (parsed.id !== requestId) {
    throw new BrainTransportError(`${context}: response id does not match the request`, {
      details: { expected: requestId, received: parsed.id },
    });
  }
  if (!parsed.ok) {
    throw new BrainApiError(parsed.error as ApiError, parsed.method ?? method, requestId);
  }
  return parsed.result;
}

/**
 * Structural validation of a response envelope that keeps `ok=false` as data.
 * Used by `request()`, where a typed Brain failure is a result, not a throw.
 */
export function validateResponseEnvelope(
  raw: unknown,
  requestId: string,
  context: string,
): ApiResponse {
  const parsed = parseApiResponse(raw, context);
  if (parsed.id !== requestId) {
    throw new BrainTransportError(`${context}: response id does not match the request`, {
      details: { expected: requestId, received: parsed.id },
    });
  }
  return raw as ApiResponse;
}

export function requestBody(raw: string, context: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    throw new BrainTransportError(`${context}: response body is not valid JSON`, {
      details: { preview: raw.slice(0, 200) },
    });
  }
}
