import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import { settingUpsertSchema, settingsService } from "@/modules/settings";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    return apiData(await settingsService.list(), requestId);
  });
}

export async function PUT(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const input = await parseJsonBody(request, settingUpsertSchema);
    return apiData(
      await settingsService.upsert(
        input.key,
        input.value as Parameters<typeof settingsService.upsert>[1],
      ),
      requestId,
    );
  });
}
