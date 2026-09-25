import { NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { apiData, withApiErrors } from "@/lib/api/response";
import { connectorService } from "@/modules/connectors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    return apiData(await connectorService.list(), requestId);
  });
}
