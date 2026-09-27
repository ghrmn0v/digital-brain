import { NextRequest } from "next/server";
import { z } from "zod";
import { requireLocalUser } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";
import { apiData, withApiErrors } from "@/lib/api/response";
import { flyControl, flyStatus, type FlyAction } from "@/lib/fly-service";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Read Fly's status, or start/stop it.
 *
 * Starting and stopping a process is a real capability, so it is deliberately
 * narrow: local user only, a fixed verb from an allowlist, and no value from the
 * request reaches a shell. Fly binds loopback and is only ever started with the
 * Brain's own environment file, so there is nothing to configure at call time
 * and nothing to leak back.
 */
const actionSchema = z.object({ action: z.enum(["start", "stop"]) }).strict();

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    requireLocalUser(request);
    return apiData(await flyStatus(), requestId);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    requireLocalUser(request);
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      throw new ApiError(400, "BAD_REQUEST", "Expected a JSON body.");
    }
    const parsed = actionSchema.safeParse(body);
    if (!parsed.success) {
      throw new ApiError(
        400,
        "INVALID_ACTION",
        'action must be exactly "start" or "stop".',
      );
    }
    const result = await flyControl(parsed.data.action as FlyAction);
    return apiData(result, requestId);
  });
}
