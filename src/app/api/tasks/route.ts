import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { executeIdempotently } from "@/lib/api/idempotency";
import { parseJsonBody, parsePagination, readIdempotencyKey } from "@/lib/api/request";
import { apiData, apiPaginated, withApiErrors } from "@/lib/api/response";
import {
  taskCreateSchema,
  taskListQuerySchema,
  taskService,
  type TaskDto,
} from "@/modules/tasks";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { page, limit } = parsePagination(request);
    const query = taskListQuerySchema.parse({
      q: request.nextUrl.searchParams.get("q") ?? undefined,
      status: request.nextUrl.searchParams.get("status") ?? undefined,
      priority: request.nextUrl.searchParams.get("priority") ?? undefined,
    });
    const result = await taskService.list(query, page, limit);
    return apiPaginated(result.items, requestId, result.pagination);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    const actor = authorizeRequest(request);
    const input = await parseJsonBody(request, taskCreateSchema);
    const idempotencyKey = readIdempotencyKey(request);
    const result = await executeIdempotently<TaskDto>({
      scope: `tasks:create:${actor.id}`,
      key: idempotencyKey,
      request: input,
      operation: async () => ({
        value: await taskService.create(input),
        statusCode: 201,
      }),
    });

    return apiData(result.value, requestId, {
      status: result.statusCode,
      headers: result.replayed ? { "idempotency-replayed": "true" } : undefined,
    });
  });
}
