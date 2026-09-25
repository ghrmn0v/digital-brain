/**
 * WebSocket transport client: one bidirectional connection to
 * `ws://host/v1/brain?user_id=...` carrying `kind`-tagged response and event
 * frames.
 *
 * Protocol rules this client enforces (see `docs/websocket-transport.md`):
 *
 * - the connection `user_id` query is the routing identity; a differing
 *   `params.user_id` is rejected locally instead of wasting a round trip on a
 *   server-side `bad_request`;
 * - the Core allows **one outstanding response per connection**, so requests
 *   are serialized on an internal queue;
 * - every request gets exactly one response frame, matched by `ApiRequest.id`;
 * - events are delivered at-most-once, deduplicated by `BrainEvent.id`,
 *   filtered by the connection identity, in arrival order.
 *
 * The socket implementation is injectable so the client can be tested without
 * a server; the default is the platform `WebSocket` global, available in
 * browsers, React Native and Node 22+.
 */

import type {
  ApiMethod,
  ApiResponse,
  BrainEvent,
  JsonObject,
  MethodParams,
  MethodResult,
} from "./contract.ts";
import {
  DEFAULT_CONNECT_TIMEOUT_MS,
  DEFAULT_DEDUPE_CAPACITY,
  DEFAULT_REQUEST_TIMEOUT_MS,
  EventDispatcher,
  RequestBuilder,
  assertValidUserId,
  buildUserIdQuery,
  correlationIdOf,
  isEventEnvelope,
  isResponseEnvelope,
  unwrapResponse,
  validateResponseEnvelope,
  type EventDispatcherStats,
  type EventHandler,
  type RequestOptions,
} from "./common.ts";
import { BrainContractError, BrainTransportError } from "./errors.ts";

export type WebSocketReadyState = 0 | 1 | 2 | 3;

export interface WebSocketLike {
  readonly readyState: number;
  binaryType?: string;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  addEventListener(type: string, listener: (event: unknown) => void): void;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export interface WebSocketBrainClientOptions {
  /** Full WebSocket URL, or a base URL that gets `/v1/brain?user_id=...` appended. */
  readonly url: string;
  /** Connection identity. Required: it is the routing and isolation key. */
  readonly userId: string;
  /** Injectable socket constructor; defaults to the platform `WebSocket`. */
  readonly socketFactory?: WebSocketFactory;
  /** Connect timeout in ms. Default 10s. */
  readonly connectTimeoutMs?: number | null;
  /** Per-request timeout in ms. Default 30s. */
  readonly requestTimeoutMs?: number | null;
  /** Deduplication window size for `BrainEvent.id`. Default 1024. */
  readonly dedupeCapacity?: number;
  /** Prefix for minted request ids. Default `brain`. */
  readonly requestIdPrefix?: string;
}

export interface WebSocketClientStats {
  readonly requestsSent: number;
  readonly responsesReceived: number;
  readonly pendingRequests: number;
  readonly eventHandlers: number;
  readonly events: Readonly<EventDispatcherStats>;
}

interface PendingRequest {
  readonly id: string;
  readonly method: string;
  readonly resolve: (value: ApiResponse) => void;
  readonly reject: (reason: unknown) => void;
  readonly timer: ReturnType<typeof setTimeout> | null;
}

export class WebSocketBrainClient {
  readonly userId: string;
  readonly supportsEvents = true;

  private readonly socketFactory: WebSocketFactory;
  private readonly url: string;
  private readonly connectTimeoutMs: number | null;
  private readonly requestTimeoutMs: number | null;
  private readonly builder: RequestBuilder;
  private readonly dispatcher: EventDispatcher;

  private socket: WebSocketLike | null = null;
  private connecting: Promise<WebSocketBrainClient> | null = null;
  private readonly pending = new Map<string, PendingRequest>();
  private queue: Promise<unknown> = Promise.resolve();
  private closed = false;
  private closeReason: string | null = null;
  private requestsSent = 0;
  private responsesReceived = 0;

  constructor(options: WebSocketBrainClientOptions) {
    this.userId = assertValidUserId(options.userId);
    this.url = buildSocketUrl(options.url, this.userId);
    const injected = options.socketFactory;
    const platformSocket = (globalThis as { WebSocket?: WebSocketFactory }).WebSocket;
    const resolved =
      injected ??
      (platformSocket === undefined
        ? undefined
        : (url: string) => new platformSocket(url) as unknown as WebSocketLike);
    if (resolved === undefined) {
      throw new BrainContractError(
        "no WebSocket implementation available; pass options.socketFactory explicitly",
      );
    }
    this.socketFactory = resolved;
    this.connectTimeoutMs =
      options.connectTimeoutMs === undefined ? DEFAULT_CONNECT_TIMEOUT_MS : options.connectTimeoutMs;
    this.requestTimeoutMs =
      options.requestTimeoutMs === undefined ? DEFAULT_REQUEST_TIMEOUT_MS : options.requestTimeoutMs;
    this.builder = new RequestBuilder({
      userId: this.userId,
      idPrefix: options.requestIdPrefix,
    });
    this.dispatcher = new EventDispatcher({
      userId: this.userId,
      dedupeCapacity: options.dedupeCapacity ?? DEFAULT_DEDUPE_CAPACITY,
    });
  }

  get readyState(): WebSocketReadyState {
    if (this.socket === null) {
      return this.closed ? 3 : 0;
    }
    return this.socket.readyState as WebSocketReadyState;
  }

  get isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === 1;
  }

  get stats(): Readonly<WebSocketClientStats> {
    return {
      requestsSent: this.requestsSent,
      responsesReceived: this.responsesReceived,
      pendingRequests: this.pending.size,
      eventHandlers: this.dispatcher.handlerCount,
      events: this.dispatcher.stats,
    };
  }

  /** Opens the connection; repeated calls share one in-flight attempt. */
  async connect(): Promise<WebSocketBrainClient> {
    if (this.socket !== null && this.socket.readyState === 1) {
      return this;
    }
    if (this.closed) {
      throw new BrainContractError("client is closed", "closed", {
        reason: this.closeReason ?? null,
      });
    }
    if (this.connecting !== null) {
      return this.connecting;
    }
    const attempt = this.open();
    this.connecting = attempt;
    try {
      return await attempt;
    } finally {
      this.connecting = null;
    }
  }

  /**
   * Subscribes to Brain events for the connection identity. Returns an
   * unsubscribe function. Handlers run synchronously in arrival order.
   */
  onEvent(handler: EventHandler): () => void {
    return this.dispatcher.subscribe(handler);
  }

  /** Correlation id of an event, for grouping related events per operation. */
  correlationIdOf(event: BrainEvent): string | null {
    return correlationIdOf(event);
  }

  /** Sends one request and returns the full `ApiResponse`; `ok=false` is returned. */
  async request<M extends ApiMethod>(
    method: M,
    params?: MethodParams<M> | JsonObject,
    options: RequestOptions = {},
  ): Promise<ApiResponse<MethodResult<M>>> {
    const prepared = await this.exchange(method, params, options);
    return validateResponseEnvelope(prepared.response, prepared.id, prepared.context) as unknown as ApiResponse<MethodResult<M>>;
  }

  /** Sends one request and returns the typed result; throws on `ok=false`. */
  async call<M extends ApiMethod>(
    method: M,
    params?: MethodParams<M> | JsonObject,
    options: RequestOptions = {},
  ): Promise<MethodResult<M>> {
    const prepared = await this.exchange(method, params, options);
    return unwrapResponse(
      prepared.response,
      method,
      prepared.id,
      prepared.context,
    ) as MethodResult<M>;
  }

  /** Closes the connection and rejects anything still in flight. */
  async close(code = 1000, reason = "client closed"): Promise<void> {
    this.closed = true;
    this.closeReason = reason;
    const socket = this.socket;
    this.socket = null;
    for (const pending of [...this.pending.values()]) {
      this.settle(pending, null, new BrainContractError(reason, "closed"));
    }
    if (socket !== null) {
      try {
        socket.close(code, reason);
      } catch {
        /* the socket is already gone */
      }
    }
  }

  private async exchange<M extends ApiMethod>(
    method: M,
    params: MethodParams<M> | JsonObject | undefined,
    options: RequestOptions,
  ): Promise<{ readonly id: string; readonly context: string; readonly response: ApiResponse }> {
    const prepared = this.builder.prepare(
      method,
      params as JsonObject | undefined,
      options,
      { enforceIdentity: true },
    );
    const send = async (): Promise<ApiResponse> => {
      await this.connect();
      const socket = this.socket;
      if (socket === null) {
        throw new BrainContractError("client is closed", "closed", {
          reason: this.closeReason ?? null,
        });
      }
      return this.dispatch(socket, prepared.envelope, prepared.id, method, options);
    };
    const response = this.queue.then(send, send);
    this.queue = response.then(
      () => undefined,
      () => undefined,
    );
    return {
      id: prepared.id,
      context: `${method} (${prepared.id})`,
      response: await response,
    };
  }

  private dispatch(
    socket: WebSocketLike,
    envelope: unknown,
    id: string,
    method: string,
    options: RequestOptions,
  ): Promise<ApiResponse> {
    const timeoutMs = options.timeoutMs === undefined ? this.requestTimeoutMs : options.timeoutMs;
    return new Promise<ApiResponse>((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout> | null = null;
      if (timeoutMs !== null && timeoutMs > 0) {
        timer = setTimeout(() => {
          this.settleById(
            id,
            null,
            new BrainTransportError(`${method}: request timed out`, {
              code: "timeout",
              details: { requestId: id, timeoutMs },
            }),
          );
        }, timeoutMs);
      }
      this.pending.set(id, { id, method, resolve, reject, timer });
      this.requestsSent += 1;
      try {
        socket.send(JSON.stringify(envelope));
      } catch (cause) {
        this.settleById(
          id,
          null,
          new BrainTransportError(
            `${method}: ${cause instanceof Error ? cause.message : String(cause)}`,
            { code: "send_failed" },
          ),
        );
      }
    });
  }

  private settleById(id: string, value: ApiResponse | null, error: unknown): void {
    const pending = this.pending.get(id);
    if (pending === undefined) {
      return;
    }
    this.settle(pending, value, error);
  }

  private settle(pending: PendingRequest, value: ApiResponse | null, error: unknown): void {
    if (!this.pending.delete(pending.id)) {
      return;
    }
    if (pending.timer !== null) {
      clearTimeout(pending.timer);
    }
    if (error === null && value !== null) {
      pending.resolve(value);
    } else {
      pending.reject(error ?? new BrainTransportError("request failed without a response"));
    }
  }

  private open(): Promise<WebSocketBrainClient> {
    return new Promise<WebSocketBrainClient>((resolve, reject) => {
      let socket: WebSocketLike;
      try {
        socket = this.socketFactory(this.url);
      } catch (cause) {
        reject(
          new BrainTransportError(
            `connect: ${cause instanceof Error ? cause.message : String(cause)}`,
            { code: "connect_failed" },
          ),
        );
        return;
      }
      this.socket = socket;
      if (typeof socket.binaryType === "string") {
        socket.binaryType = "arraybuffer";
      }

      let settled = false;
      let timer: ReturnType<typeof setTimeout> | null = null;
      const failConnect = (message: string): void => {
        if (settled) {
          return;
        }
        settled = true;
        if (timer !== null) {
          clearTimeout(timer);
        }
        this.socket = null;
        try {
          socket.close(1002, message);
        } catch {
          /* the socket never opened */
        }
        reject(new BrainTransportError(`connect: ${message}`, { code: "connect_failed" }));
      };

      if (this.connectTimeoutMs !== null && this.connectTimeoutMs > 0) {
        timer = setTimeout(() => {
          failConnect("connection timed out");
        }, this.connectTimeoutMs);
      }

      socket.addEventListener("open", () => {
        if (settled) {
          return;
        }
        settled = true;
        if (timer !== null) {
          clearTimeout(timer);
        }
        resolve(this);
      });
      socket.addEventListener("message", (event: unknown) => {
        this.onMessage(event);
      });
      socket.addEventListener("error", () => {
        failConnect("socket error before open");
      });
      socket.addEventListener("close", (event: unknown) => {
        const reason = describeClose(event);
        this.socket = null;
        if (!settled) {
          failConnect(`closed during connect: ${reason}`);
          return;
        }
        for (const pending of [...this.pending.values()]) {
          this.settle(pending, null, new BrainContractError(reason, "closed"));
        }
      });
    });
  }

  private onMessage(event: unknown): void {
    const raw = extractText(event);
    if (raw === null) {
      this.dispatcher.accept(" binary-unreadable");
      return;
    }
    const frame = this.dispatcher.accept(raw);
    if (frame === null || isEventEnvelope(frame) || !isResponseEnvelope(frame)) {
      return;
    }
    this.responsesReceived += 1;
    const payload = frame.payload;
    const id = payload.id;
    if (typeof id !== "string" || id === "") {
      return;
    }
    this.settleById(id, payload, null);
  }
}

function extractText(event: unknown): string | null {
  if (typeof event === "string") {
    return event;
  }
  if (typeof event !== "object" || event === null) {
    return null;
  }
  const data = (event as { data?: unknown }).data;
  if (typeof data === "string") {
    return data;
  }
  if (data instanceof ArrayBuffer) {
    return new TextDecoder().decode(data);
  }
  if (ArrayBuffer.isView(data)) {
    return new TextDecoder().decode(
      new Uint8Array(data.buffer, data.byteOffset, data.byteLength),
    );
  }
  if (Array.isArray(data) && data.every((chunk) => chunk instanceof Uint8Array)) {
    const total = data.reduce((sum, chunk) => sum + (chunk as Uint8Array).byteLength, 0);
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of data as Uint8Array[]) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return new TextDecoder().decode(merged);
  }
  return null;
}

function describeClose(event: unknown): string {
  if (typeof event !== "object" || event === null) {
    return "connection closed";
  }
  const record = event as { code?: unknown; reason?: unknown };
  const code = typeof record.code === "number" ? record.code : 0;
  const reason =
    typeof record.reason === "string" && record.reason !== "" ? record.reason : "no reason";
  return `connection closed (code ${code}, ${reason})`;
}

export function buildSocketUrl(url: string, userId: string): string {
  if (typeof url !== "string" || url.trim() === "") {
    throw new BrainContractError("url is required");
  }
  const base = url.endsWith("/") ? url.slice(0, -1) : url;
  if (base.includes("/v1/brain")) {
    const separator = base.includes("?") ? "&" : "?";
    return `${base}${separator}user_id=${encodeURIComponent(userId)}`;
  }
  const wsBase = base.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
  return `${wsBase}/v1/brain${buildUserIdQuery(userId)}`;
}
