import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import { actionDecisionSchema, actionService } from "@/modules/actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const actionIdSchema = z.string().min(1).max(64);

export async function POST(
  request: NextRequest,
  context: RouteContext<"/api/actions/[id]/reject">,
) {
  return withApiErrors(request, async (requestId) => {
    const actor = authorizeRequest(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, actionDecisionSchema);
    return apiData(
      await actionService.reject(actionIdSchema.parse(id), actor.id, input.reason),
      requestId,
    );
  });
}
