import { NextRequest } from "next/server";
import { requireLocalUser } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { brainService } from "@/modules/brain";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Status of the Core Brain connection plus its capability catalogue. */
export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    requireLocalUser(request);
    return apiData(await brainService.status(), requestId);
  });
}
