import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { executeIdempotently } from "@/lib/api/idempotency";
import { parseJsonBody, parsePagination, readIdempotencyKey } from "@/lib/api/request";
import { apiData, apiPaginated, withApiErrors } from "@/lib/api/response";
import {
  calendarEventCreateSchema,
  calendarEventListQuerySchema,
  calendarService,
  type CalendarEventDto,
} from "@/modules/calendar";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { page, limit } = parsePagination(request);
    const query = calendarEventListQuerySchema.parse({
      q: request.nextUrl.searchParams.get("q") ?? undefined,
      status: request.nextUrl.searchParams.get("status") ?? undefined,
      from: request.nextUrl.searchParams.get("from") ?? undefined,
      to: request.nextUrl.searchParams.get("to") ?? undefined,
    });
    const result = await calendarService.list(query, page, limit);
    return apiPaginated(result.items, requestId, result.pagination);
  });
}

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    const actor = authorizeRequest(request);
    const input = await parseJsonBody(request, calendarEventCreateSchema);
    const result = await executeIdempotently<CalendarEventDto>({
      scope: `calendar:create:${actor.id}`,
      key: readIdempotencyKey(request),
      request: input,
      operation: async () => ({
        value: await calendarService.create(input),
        statusCode: 201,
      }),
    });

    return apiData(result.value, requestId, {
      status: result.statusCode,
      headers: result.replayed ? { "idempotency-replayed": "true" } : undefined,
    });
  });
}
