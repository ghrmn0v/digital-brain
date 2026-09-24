import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { actionService } from "@/modules/actions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const actionIdSchema = z.string().min(1).max(64);

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/actions/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(await actionService.get(actionIdSchema.parse(id)), requestId);
  });
}
