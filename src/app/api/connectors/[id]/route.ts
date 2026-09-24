import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  connectorService,
  connectorUpdateSchema,
} from "@/modules/connectors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const connectorIdSchema = z.string().min(1).max(64);

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/connectors/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    return apiData(
      await connectorService.get(connectorIdSchema.parse(id)),
      requestId,
    );
  });
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext<"/api/connectors/[id]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { id } = await context.params;
    const input = await parseJsonBody(request, connectorUpdateSchema);
    return apiData(
      await connectorService.setEnabled(connectorIdSchema.parse(id), input.enabled),
      requestId,
    );
  });
}
