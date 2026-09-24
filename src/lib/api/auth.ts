import { timingSafeEqual } from "node:crypto";
import { ApiError } from "@/lib/api/errors";

export type RequestActor = {
  kind: "local_user" | "service";
  id: string;
};

function safeTokenMatch(provided: string, expected: string): boolean {
  const providedBuffer = Buffer.from(provided);
  const expectedBuffer = Buffer.from(expected);
  return (
    providedBuffer.length === expectedBuffer.length &&
    timingSafeEqual(providedBuffer, expectedBuffer)
  );
}

function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (origin) {
    try {
      return new URL(origin).host === request.headers.get("host");
    } catch {
      return false;
    }
  }

  if (process.env.NODE_ENV !== "production") return true;
  return request.headers.get("sec-fetch-site") === "same-origin";
}

function readBearerToken(request: Request): string | null {
  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Bearer ")) return null;
  return authorization.slice("Bearer ".length).trim() || null;
}

export function authorizeRequest(request: Request): RequestActor {
  const configuredToken = process.env.SERVICE_API_TOKEN?.trim();
  const bearerToken = readBearerToken(request);

  if (configuredToken && bearerToken) {
    if (safeTokenMatch(bearerToken, configuredToken)) {
      return { kind: "service", id: "service-api" };
    }
    throw new ApiError(401, "INVALID_SERVICE_TOKEN", "Invalid service token.");
  }

  if (isSameOrigin(request)) {
    return { kind: "local_user", id: "local-user" };
  }

  if (process.env.NODE_ENV !== "production") {
    return { kind: "local_user", id: "local-user" };
  }

  if (configuredToken) {
    throw new ApiError(
      401,
      "AUTHENTICATION_REQUIRED",
      "A valid service token is required.",
    );
  }

  throw new ApiError(
    403,
    "LOCAL_REQUEST_REQUIRED",
    "This endpoint only accepts local same-origin or authenticated service requests.",
  );
}
