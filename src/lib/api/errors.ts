export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;
  readonly expose: boolean;

  constructor(
    status: number,
    code: string,
    message: string,
    options?: { cause?: unknown; details?: unknown; expose?: boolean },
  ) {
    super(message, options?.cause ? { cause: options.cause } : undefined);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = options?.details;
    this.expose = options?.expose ?? status < 500;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
