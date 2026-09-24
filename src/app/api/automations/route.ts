import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  automationCreateSchema,
  automationListQuerySchema,
  automationService,
} from "@/modules/automations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const query = automationListQuerySchema.parse({
      enabled: request.nextUrl.searchParams.get("enabled") ?? undefined,
      triggerKind:
        request.nextUrl.searchParams.get("triggerKind") ?? undefined,
    });
    return apiData(await automationService.list(query), requestId);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const input = await parseJsonBody(request, automationCreateSchema);
    return apiData(await automationService.create(input), requestId);
  });
}
