import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import {
  apiData,
  apiNoContent,
  withApiErrors,
} from "@/lib/api/response";
import { taskService, taskUpdateSchema } from "@/modules/tasks";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const taskIdSchema = z.string().min(1).max(64);

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/tasks/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const taskId = taskIdSchema.parse(id);
    return apiData(await taskService.get(taskId), requestId);
  });
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext<"/api/tasks/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const taskId = taskIdSchema.parse(id);
    const input = await parseJsonBody(request, taskUpdateSchema);
    return apiData(await taskService.update(taskId, input), requestId);
  });
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext<"/api/tasks/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const taskId = taskIdSchema.parse(id);
    await taskService.remove(taskId);
    return apiNoContent(requestId);
  });
}
