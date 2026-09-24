import { z } from "zod";
import { ApiError } from "@/lib/api/errors";

const DEFAULT_MAX_BODY_BYTES = 1_000_000;

export async function parseJsonBody<TSchema extends z.ZodType>(
  request: Request,
  schema: TSchema,
  maxBytes = DEFAULT_MAX_BODY_BYTES,
): Promise<z.infer<TSchema>> {
  const contentType = request.headers.get("content-type")?.split(";", 1)[0];
  if (contentType !== "application/json") {
    throw new ApiError(
      415,
      "UNSUPPORTED_MEDIA_TYPE",
      "Content-Type must be application/json.",
    );
  }

  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > maxBytes) {
    throw new ApiError(413, "PAYLOAD_TOO_LARGE", "Request body is too large.");
  }

  const rawBody = await request.text();
  if (Buffer.byteLength(rawBody, "utf8") > maxBytes) {
    throw new ApiError(413, "PAYLOAD_TOO_LARGE", "Request body is too large.");
  }

  let body: unknown;
  try {
    body = JSON.parse(rawBody) as unknown;
  } catch {
    throw new ApiError(400, "INVALID_JSON", "Request body is not valid JSON.");
  }

  const result = schema.safeParse(body);
  if (!result.success) {
    throw new ApiError(400, "VALIDATION_ERROR", "Request validation failed.", {
      details: result.error.flatten(),
    });
  }

  return result.data;
}

export function parsePagination(
  request: Request,
  defaultLimit = 25,
  maxLimit = 100,
) {
  const searchParams = new URL(request.url).searchParams;
  const pageValue = searchParams.get("page") ?? "1";
  const limitValue = searchParams.get("limit") ?? String(defaultLimit);
  const result = z
    .object({
      page: z.coerce.number().int().min(1),
      limit: z.coerce.number().int().min(1).max(maxLimit),
    })
    .safeParse({ page: pageValue, limit: limitValue });

  if (!result.success) {
    throw new ApiError(400, "INVALID_PAGINATION", "Invalid pagination values.");
  }

  return result.data;
}

export function readIdempotencyKey(request: Request): string | undefined {
  const value = request.headers.get("idempotency-key")?.trim();
  if (!value) return undefined;
  if (value.length > 128) {
    throw new ApiError(
      400,
      "INVALID_IDEMPOTENCY_KEY",
      "Idempotency-Key must be at most 128 characters.",
    );
  }
  return value;
}
