import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { jobReportQuerySchema, jobService } from "@/modules/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const query = jobReportQuerySchema.parse({
      since: request.nextUrl.searchParams.get("since") ?? undefined,
    });
    return apiData(
      await jobService.report(query.since ? new Date(query.since) : undefined),
      requestId,
    );
  });
}
