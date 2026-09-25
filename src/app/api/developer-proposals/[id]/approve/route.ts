import { NextRequest } from "next/server";
import { z } from "zod";
import { requireLocalUser } from "@/lib/api/auth";
import { requireDesktopClient } from "@/lib/api/platform";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  developerDecisionSchema,
  developerModeService,
} from "@/modules/developer-mode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const proposalIdSchema = z.string().min(1).max(64);

export async function POST(
  request: NextRequest,
  context: RouteContext<"/api/developer-proposals/[id]/approve">,
) {
  return withApiErrors(request, async (requestId) => {
    const actor = requireLocalUser(request);
    requireDesktopClient(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, developerDecisionSchema);
    return apiData(
      await developerModeService.approve(
        proposalIdSchema.parse(id),
        actor.id,
        input.reason,
      ),
      requestId,
    );
  });
}
