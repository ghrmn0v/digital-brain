/**
 * Client-side error types.
 *
 * Three failure classes are kept separate on purpose:
 *
 * - `BrainApiError` — the Brain answered with `ok=false`. The canonical
 *   `ApiError` is preserved verbatim; callers branch on `error.code`, never on
 *   an HTTP status.
 * - `BrainTransportError` — the request never produced a valid `ApiResponse`
 *   (network failure, timeout, unparsable body, wrong endpoint).
 * - `BrainContractError` — a local precondition failed before anything was
 *   sent (invalid identity, conflicting `user_id`, closed connection).
 */

import type { ApiError, ApiErrorCode } from "./contract.ts";

export type BrainClientErrorKind =
  | "api"
  | "transport"
  | "contract"
  | "identity"
  | "closed"
  | "timeout";

export class BrainClientError extends Error {
  readonly kind: BrainClientErrorKind;
  readonly code: string | null;
  readonly details: Readonly<Record<string, unknown>>;

  constructor(
    kind: BrainClientErrorKind,
    message: string,
    code: string | null = null,
    details: Readonly<Record<string, unknown>> = {},
  ) {
    super(message);
    this.name = "BrainClientError";
    this.kind = kind;
    this.code = code;
    this.details = details;
  }
}

export class BrainApiError extends BrainClientError {
  readonly error: ApiError;
  readonly method: string | null;

  constructor(error: ApiError, method: string | null, requestId: string) {
    super("api", error.message, error.code, {
      ...error.details,
      requestId,
      source: error.source ?? null,
    });
    this.name = "BrainApiError";
    this.error = error;
    this.method = method;
  }

  get typedCode(): ApiErrorCode | null {
    const code = this.error.code;
    return isApiErrorCode(code) ? code : null;
  }
}

export class BrainTransportError extends BrainClientError {
  readonly status: number | null;

  constructor(
    message: string,
    options: {
      readonly status?: number | null;
      readonly code?: string | null;
      readonly details?: Readonly<Record<string, unknown>>;
    } = {},
  ) {
    super("transport", message, options.code ?? null, options.details ?? {});
    this.name = "BrainTransportError";
    this.status = options.status ?? null;
  }
}

export class BrainContractError extends BrainClientError {
  constructor(
    message: string,
    kind: "contract" | "identity" = "contract",
    details: Readonly<Record<string, unknown>> = {},
  ) {
    super(kind, message, null, details);
    this.name = "BrainContractError";
  }
}

/**
 * The client (or the connection) was closed, so a request can no longer be
 * completed. This is a lifecycle condition, not a contract violation and not a
 * transport failure, which is why it has its own class while still carrying the
 * documented `BrainClientErrorKind` of `"closed"`.
 */
export class BrainClosedError extends BrainClientError {
  constructor(
    message: string,
    details: Readonly<Record<string, unknown>> = {},
  ) {
    super("closed", message, null, details);
    this.name = "BrainClosedError";
  }
}

export function isApiErrorCode(value: string): value is ApiErrorCode {
  return (
    value === "bad_request" ||
    value === "unknown_method" ||
    value === "version_unsupported" ||
    value === "validation_error" ||
    value === "not_configured" ||
    value === "internal_error"
  );
}

export function isBrainApiError(value: unknown): value is BrainApiError {
  return value instanceof BrainApiError;
}

export function isBrainClientError(value: unknown): value is BrainClientError {
  return value instanceof BrainClientError;
}
