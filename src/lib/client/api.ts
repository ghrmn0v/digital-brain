export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    requestId?: string;
    details?: unknown;
  };
}

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly details: unknown;

  constructor(options: {
    message: string;
    status: number;
    code?: string;
    requestId?: string | null;
    details?: unknown;
  }) {
    super(options.message);
    this.name = "ApiRequestError";
    this.status = options.status;
    this.code = options.code ?? `HTTP_${options.status}`;
    this.requestId = options.requestId ?? null;
    this.details = options.details;
  }
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (!value || typeof value !== "object" || !("error" in value)) return false;
  return typeof (value as ApiErrorPayload).error === "object";
}

function isDataEnvelope(value: unknown): value is { data: unknown } {
  return Boolean(
    value &&
      typeof value === "object" &&
      "data" in value &&
      (value as { data?: unknown }).data !== undefined,
  );
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;

  const text = await response.text();
  if (!text) return undefined;

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

/**
 * Calls a local Product API and unwraps the standard `{ data, meta }` envelope.
 * Expected API failures are normalized as ApiRequestError for UI feedback.
 */
export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { body, headers: suppliedHeaders, ...requestInit } = options;
  const headers = new Headers(suppliedHeaders);
  headers.set("accept", "application/json");

  if (body !== undefined) {
    headers.set("content-type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...requestInit,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch (error) {
    throw new ApiRequestError({
      message:
        error instanceof Error
          ? `Unable to reach the Product API: ${error.message}`
          : "Unable to reach the Product API.",
      status: 0,
      code: "NETWORK_ERROR",
    });
  }

  const payload = await parseResponseBody(response);

  if (!response.ok) {
    const apiError = isApiErrorPayload(payload) ? payload.error : undefined;
    throw new ApiRequestError({
      message:
        apiError?.message?.trim() ||
        `Product API request failed with status ${response.status}.`,
      status: response.status,
      code: apiError?.code,
      requestId: apiError?.requestId,
      details: apiError?.details,
    });
  }

  if (response.status === 204) return undefined as T;

  if (!isDataEnvelope(payload)) {
    throw new ApiRequestError({
      message: "Product API returned an invalid response envelope.",
      status: response.status,
      code: "INVALID_RESPONSE",
    });
  }

  return payload.data as T;
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) return error.message;
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}
