import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  connectorHealthSchema,
  connectorService,
} from "@/modules/connectors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const connectorIdSchema = z.string().min(1).max(64);

export async function POST(
  request: NextRequest,
  context: RouteContext<"/api/internal/connectors/[id]/health">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, connectorHealthSchema);
    return apiData(
      await connectorService.recordHealth(
        connectorIdSchema.parse(id),
        input.status,
        input.lastSyncAt == null ? null : new Date(input.lastSyncAt),
        input.message,
      ),
      requestId,
    );
  });
}
