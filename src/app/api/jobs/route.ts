import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody, parsePagination } from "@/lib/api/request";
import { apiData, apiPaginated, withApiErrors } from "@/lib/api/response";
import { jobListQuerySchema, jobService, jobUpsertSchema } from "@/modules/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { page, limit } = parsePagination(request);
    const query = jobListQuerySchema.parse({
      q: request.nextUrl.searchParams.get("q") ?? undefined,
      source: request.nextUrl.searchParams.get("source") ?? undefined,
      status: request.nextUrl.searchParams.get("status") ?? undefined,
      company: request.nextUrl.searchParams.get("company") ?? undefined,
    });
    const result = await jobService.list(query, page, limit);
    return apiPaginated(result.items, requestId, result.pagination);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const input = await parseJsonBody(request, jobUpsertSchema);
    return apiData(await jobService.upsert(input), requestId);
  });
}
