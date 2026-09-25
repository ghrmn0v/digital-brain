import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { timelineQuerySchema, timelineService } from "@/modules/timeline";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const query = timelineQuerySchema.parse({
      kind: request.nextUrl.searchParams.get("kind") ?? undefined,
      limit: request.nextUrl.searchParams.get("limit") ?? undefined,
    });
    return apiData(
      await timelineService.list(query.kind, query.limit),
      requestId,
    );
  });
}
