import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { automationService } from "@/modules/automations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const automationIdSchema = z.string().min(1).max(64);

export async function POST(
  request: NextRequest,
  context: RouteContext<"/api/automations/[id]/run">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(
      await automationService.runManually(automationIdSchema.parse(id)),
      requestId,
    );
  });
}
