import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  permissionListQuerySchema,
  permissionService,
  permissionUpsertSchema,
} from "@/modules/permissions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const query = permissionListQuerySchema.parse({
      source: request.nextUrl.searchParams.get("source") ?? undefined,
      action: request.nextUrl.searchParams.get("action") ?? undefined,
      enabled: request.nextUrl.searchParams.get("enabled") ?? undefined,
    });
    return apiData(await permissionService.list(query), requestId);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const input = await parseJsonBody(request, permissionUpsertSchema);
    return apiData(await permissionService.upsert(input), requestId);
  });
}
