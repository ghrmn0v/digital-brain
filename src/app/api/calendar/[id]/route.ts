import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, apiNoContent, withApiErrors } from "@/lib/api/response";
import {
  calendarEventUpdateSchema,
  calendarService,
} from "@/modules/calendar";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const eventIdSchema = z.string().min(1).max(64);

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/calendar/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(await calendarService.get(eventIdSchema.parse(id)), requestId);
  });
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext<"/api/calendar/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, calendarEventUpdateSchema);
    return apiData(
      await calendarService.update(eventIdSchema.parse(id), input),
      requestId,
    );
  });
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext<"/api/calendar/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    await calendarService.remove(eventIdSchema.parse(id));
    return apiNoContent(requestId);
  });
}
