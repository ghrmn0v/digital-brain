import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { eventDeliveryService } from "@/modules/events";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    const actor = authorizeRequest(request);
    await eventDeliveryService.processPending(25);
    return apiData({ processed: true, actor: actor.kind }, requestId);
  });
}
