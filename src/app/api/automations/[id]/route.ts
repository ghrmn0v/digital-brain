import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, apiNoContent, withApiErrors } from "@/lib/api/response";
import {
  automationService,
  automationUpdateSchema,
} from "@/modules/automations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const automationIdSchema = z.string().min(1).max(64);

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/automations/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(
      await automationService.get(automationIdSchema.parse(id)),
      requestId,
    );
  });
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext<"/api/automations/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, automationUpdateSchema);
    return apiData(
      await automationService.update(automationIdSchema.parse(id), input),
      requestId,
    );
  });
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext<"/api/automations/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    await automationService.remove(automationIdSchema.parse(id));
    return apiNoContent(requestId);
  });
}
