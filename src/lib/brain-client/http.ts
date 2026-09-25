/**
 * HTTP transport client: `POST {baseUrl}/v1/brain` with one `ApiRequest` per
 * call, plus the static `GET {baseUrl}/health` liveness probe.
 *
 * The bundled HTTP transport has no event stream (its CLI wires
 * `NullEventSink`), so this client is request/response only. Use
 * `WebSocketBrainClient` when live events are needed.
 *
 * Only the platform `fetch` global is used, so the same source runs in a
 * browser, in a React Native app and in Node 22+.
 */

import type {
  ApiMethod,
  ApiResponse,
  HealthPayload,
  JsonObject,
  MethodParams,
  MethodResult,
} from "./contract.ts";
import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  RequestBuilder,
  joinUrl,
  requestBody,
  unwrapResponse,
  validateResponseEnvelope,
  type RequestOptions,
} from "./common.ts";
import { BrainContractError, BrainTransportError } from "./errors.ts";

export type FetchLike = (
  input: string,
  init?: {
    readonly method?: string;
    readonly headers?: Record<string, string>;
    readonly body?: string;
    readonly signal?: AbortSignal;
  },
) => Promise<{
  readonly status: number;
  readonly ok: boolean;
  text(): Promise<string>;
}>;

export interface HttpBrainClientOptions {
  /** Base URL of a running `core.transport.http` server, e.g. `http://127.0.0.1:8765`. */
  readonly baseUrl: string;
  /** Default identity injected into methods whose params carry `user_id`. */
  readonly userId?: string | null;
  /** Injectable for tests; defaults to the platform `fetch`. */
  readonly fetch?: FetchLike;
  /** Per-request timeout, `null` disables it. Default 30s. */
  readonly requestTimeoutMs?: number | null;
  /** Prefix for minted request ids. Default `brain`. */
  readonly requestIdPrefix?: string;
  /** Extra headers, e.g. an auth header added by the product's own session layer. */
  readonly headers?: Readonly<Record<string, string>>;
}

export class HttpBrainClient {
  readonly baseUrl: string;
  readonly userId: string | null;
  readonly supportsEvents = false;

  private readonly fetchImpl: FetchLike;
  private readonly timeoutMs: number | null;
  private readonly builder: RequestBuilder;
  private readonly headers: Readonly<Record<string, string>>;

  constructor(options: HttpBrainClientOptions) {
    if (typeof options.baseUrl !== "string" || options.baseUrl.trim() === "") {
      throw new BrainContractError("baseUrl is required");
    }
    this.baseUrl = options.baseUrl.endsWith("/") ? options.baseUrl.slice(0, -1) : options.baseUrl;
    this.userId = options.userId ?? null;
    const injected = options.fetch;
    const platformFetch = (globalThis as { fetch?: FetchLike }).fetch;
    const resolved = injected ?? platformFetch;
    if (resolved === undefined) {
      throw new BrainContractError(
        "no fetch implementation available; pass options.fetch explicitly",
      );
    }
    this.fetchImpl = resolved;
    this.timeoutMs = options.requestTimeoutMs === undefined ? DEFAULT_REQUEST_TIMEOUT_MS : options.requestTimeoutMs;
    this.builder = new RequestBuilder({
      userId: this.userId,
      idPrefix: options.requestIdPrefix,
    });
    this.headers = options.headers ?? {};
  }

  /** `GET /health` — static liveness payload, no user data. */
  async health(): Promise<HealthPayload> {
    const url = joinUrl(this.baseUrl, "/health");
    const response = await this.send(url, "GET", undefined, this.timeoutMs);
    const parsed = requestBody(await response.text(), "health");
    if (typeof parsed !== "object" || parsed === null) {
      throw new BrainTransportError("health: response is not a JSON object", {
        status: response.status,
      });
    }
    return parsed as unknown as HealthPayload;
  }

  /**
   * Sends one request and returns the full `ApiResponse`. Protocol-level
   * failures (`ok=false`) are returned, not thrown.
   */
  async request<M extends ApiMethod>(
    method: M,
    params?: MethodParams<M> | JsonObject,
    options: RequestOptions = {},
  ): Promise<ApiResponse<MethodResult<M>>> {
    const exchange = await this.exchange(method, params, options);
    return validateResponseEnvelope(exchange.parsed, exchange.id, exchange.context) as unknown as ApiResponse<MethodResult<M>>;
  }

  /** Same as `request`, but returns the typed result and throws on `ok=false`. */
  async call<M extends ApiMethod>(
    method: M,
    params?: MethodParams<M> | JsonObject,
    options: RequestOptions = {},
  ): Promise<MethodResult<M>> {
    const exchange = await this.exchange(method, params, options);
    return unwrapResponse(
      exchange.parsed,
      method,
      exchange.id,
      exchange.context,
    ) as MethodResult<M>;
  }

  /** No connection state to release; present so both clients share a shape. */
  close(): void {}

  private async exchange<M extends ApiMethod>(
    method: M,
    params: MethodParams<M> | JsonObject | undefined,
    options: RequestOptions,
  ): Promise<{ readonly id: string; readonly context: string; readonly parsed: unknown }> {
    const prepared = this.builder.prepare(method, params as JsonObject | undefined, options);
    const url = joinUrl(this.baseUrl, "/v1/brain");
    const response = await this.send(
      url,
      "POST",
      JSON.stringify(prepared.envelope),
      options.timeoutMs === undefined ? this.timeoutMs : options.timeoutMs,
    );
    const context = `${method} (${prepared.id})`;
    const raw = await response.text();
    const parsed = requestBody(raw, context);
    if (typeof parsed === "object" && parsed !== null && !("id" in parsed) && !("ok" in parsed)) {
      throw new BrainTransportError(`${context}: endpoint is not a Brain API endpoint`, {
        status: response.status,
        details: { preview: raw.slice(0, 200) },
      });
    }
    return { id: prepared.id, context, parsed };
  }

  private async send(
    url: string,
    method: "GET" | "POST",
    body: string | undefined,
    timeoutMs: number | null,
  ): Promise<{ readonly status: number; readonly ok: boolean; text(): Promise<string> }> {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    if (controller !== null && timeoutMs !== null && timeoutMs > 0) {
      timer = setTimeout(() => {
        controller.abort();
      }, timeoutMs);
    }
    const headers: Record<string, string> = {
      accept: "application/json",
      ...this.headers,
    };
    if (body !== undefined) {
      headers["content-type"] = "application/json";
    }
    try {
      return await this.fetchImpl(url, {
        method,
        headers,
        ...(body === undefined ? {} : { body }),
        ...(controller === null ? {} : { signal: controller.signal }),
      });
    } catch (cause) {
      if (controller !== null && controller.signal.aborted) {
        throw new BrainTransportError(`${method} ${url}: request timed out`, {
          code: "timeout",
          details: { timeoutMs },
        });
      }
      throw new BrainTransportError(`${method} ${url}: ${describe(cause)}`, {
        code: "network_error",
      });
    } finally {
      if (timer !== null) {
        clearTimeout(timer);
      }
    }
  }
}

function describe(cause: unknown): string {
  if (cause instanceof Error) {
    return cause.message;
  }
  return String(cause);
}
