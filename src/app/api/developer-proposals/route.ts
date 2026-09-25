import { NextRequest } from "next/server";
import { z } from "zod";
import { requireLocalUser } from "@/lib/api/auth";
import { requireDesktopClient } from "@/lib/api/platform";
import { apiData, withApiErrors } from "@/lib/api/response";
import { developerModeService } from "@/modules/developer-mode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const querySchema = z.object({
  limit: z.coerce.number().int().min(1).max(200).default(100),
});

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    requireLocalUser(request);
    requireDesktopClient(request);
    const query = querySchema.parse({
      limit: request.nextUrl.searchParams.get("limit") ?? undefined,
    });
    const enabled = await developerModeService.isEnabled();
    return apiData(
      {
        enabled,
        proposals: enabled
          ? await developerModeService.listProposals(query.limit)
          : [],
      },
      requestId,
    );
  });
}
