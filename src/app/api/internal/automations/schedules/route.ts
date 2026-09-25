import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { automationService } from "@/modules/automations";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    return apiData(await automationService.processSchedules(), requestId);
  });
}
