import { NextRequest } from "next/server";
import { requireLocalUser } from "@/lib/api/auth";
import { requireDesktopClient } from "@/lib/api/platform";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import {
  developerModeService,
  developerModeUpdateSchema,
} from "@/modules/developer-mode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    requireLocalUser(request);
    requireDesktopClient(request);
    return apiData(
      { enabled: await developerModeService.isEnabled() },
      requestId,
    );
  });
}

export async function PUT(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    const actor = requireLocalUser(request);
    requireDesktopClient(request);
    const input = await parseJsonBody(request, developerModeUpdateSchema);
    const result = await developerModeService.setEnabled(input.enabled);
    return apiData(
      {
        ...result,
        updatedBy: actor.id,
      },
      requestId,
    );
  });
}
