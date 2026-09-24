import { NextRequest } from "next/server";
import { z } from "zod";
import { authorizeRequest } from "@/lib/api/auth";
import { apiNoContent, withApiErrors } from "@/lib/api/response";
import { settingsService } from "@/modules/settings";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const settingKeySchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[a-z0-9]+(?:[._-][a-z0-9]+)*$/);

export async function DELETE(
  request: NextRequest,
  context: RouteContext<"/api/settings/[key]">,
) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const { key } = await context.params;
    await settingsService.remove(settingKeySchema.parse(key));
    return apiNoContent(requestId);
  });
}
