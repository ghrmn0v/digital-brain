import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import { jobService, jobUpdateSchema } from "@/modules/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const jobIdSchema = z.string().min(1).max(64);

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/jobs/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(await jobService.get(jobIdSchema.parse(id)), requestId);
  });
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext<"/api/jobs/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, jobUpdateSchema);
    return apiData(await jobService.update(jobIdSchema.parse(id), input), requestId);
  });
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext<"/api/jobs/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(await jobService.archive(jobIdSchema.parse(id)), requestId);
  });
}
