import { randomUUID } from "node:crypto";
import { ZodError } from "zod";
import { Prisma } from "@/generated/prisma/client";
import { isApiError } from "@/lib/api/errors";

export interface ApiMeta {
  requestId: string;
  pagination?: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    requestId: string;
    details?: unknown;
  };
}

export function getRequestId(request: Request): string {
  const supplied = request.headers.get("x-request-id")?.trim();
  return supplied && supplied.length <= 128 ? supplied : randomUUID();
}

function versionedInit(init?: ResponseInit): ResponseInit {
  const headers = new Headers(init?.headers);
  headers.set("x-product-api-version", "1.0");
  return { ...init, headers };
}

export function apiData<T>(data: T, requestId: string, init?: ResponseInit) {
  return Response.json(
    { data, meta: { requestId } satisfies ApiMeta },
    versionedInit(init),
  );
}

export function apiPaginated<T>(
  data: T,
  requestId: string,
  pagination: NonNullable<ApiMeta["pagination"]>,
) {
  return Response.json(
    {
      data,
      meta: { requestId, pagination } satisfies ApiMeta,
    },
    versionedInit(),
  );
}

export function apiCreated<T>(data: T, requestId: string) {
  return apiData(data, requestId, { status: 201 });
}

export function apiNoContent(requestId?: string) {
  return new Response(null, {
    status: 204,
    headers: versionedInit(
      requestId ? { headers: { "x-request-id": requestId } } : undefined,
    ).headers,
  });
}

export async function handleApiError(
  error: unknown,
  requestId: string,
): Promise<Response> {
  if (isApiError(error)) {
    return Response.json(
      {
        error: {
          code: error.code,
          message: error.message,
          requestId,
          ...(error.expose && error.details !== undefined
            ? { details: error.details }
            : {}),
        },
      } satisfies ApiErrorBody,
      versionedInit({ status: error.status }),
    );
  }

  if (error instanceof Prisma.PrismaClientKnownRequestError) {
    if (error.code === "P2002") {
      return Response.json(
        {
          error: {
            code: "RESOURCE_CONFLICT",
            message: "A resource with the same unique identity already exists.",
            requestId,
          },
        } satisfies ApiErrorBody,
        versionedInit({ status: 409 }),
      );
    }
    if (error.code === "P2025") {
      return Response.json(
        {
          error: {
            code: "RESOURCE_NOT_FOUND",
            message: "The requested resource was not found.",
            requestId,
          },
        } satisfies ApiErrorBody,
        versionedInit({ status: 404 }),
      );
    }
  }

  if (error instanceof ZodError) {
    return Response.json(
      {
        error: {
          code: "VALIDATION_ERROR",
          message: "Request validation failed.",
          requestId,
          details: error.flatten(),
        },
      } satisfies ApiErrorBody,
      versionedInit({ status: 400 }),
    );
  }

  console.error("Unhandled API error.", { requestId, error });
  return Response.json(
    {
      error: {
        code: "INTERNAL_ERROR",
        message: "An unexpected error occurred.",
        requestId,
      },
    } satisfies ApiErrorBody,
    versionedInit({ status: 500 }),
  );
}

export async function withApiErrors(
  request: Request,
  handler: (requestId: string) => Promise<Response>,
): Promise<Response> {
  const requestId = getRequestId(request);
  try {
    return await handler(requestId);
  } catch (error) {
    return handleApiError(error, requestId);
  }
}
