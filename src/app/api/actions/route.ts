import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody, parsePagination, readIdempotencyKey } from "@/lib/api/request";
import { apiData, apiPaginated, withApiErrors } from "@/lib/api/response";
import { actionRequestSchema } from "@/lib/actions";
import {
  actionExecutionListQuerySchema,
  actionService,
} from "@/modules/actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { page, limit } = parsePagination(request);
    const query = actionExecutionListQuerySchema.parse({
      status: request.nextUrl.searchParams.get("status") ?? undefined,
      source: request.nextUrl.searchParams.get("source") ?? undefined,
      action: request.nextUrl.searchParams.get("action") ?? undefined,
    });
    const result = await actionService.list(query, page, limit);
    return apiPaginated(result.items, requestId, result.pagination);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const input = await parseJsonBody(request, actionRequestSchema);
    const response = await actionService.request(input, readIdempotencyKey(request));
    return apiData(response, requestId, {
      status: response.status === "pending_approval" ? 202 : 200,
    });
  });
}
