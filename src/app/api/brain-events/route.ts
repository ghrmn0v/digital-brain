import { after, NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiCreated, withApiErrors } from "@/lib/api/response";
import {
  normalizedEventSchema,
  type NormalizedEvent,
} from "@/lib/events";
import {
  developerBugDetectedPayloadSchema,
  developerModeService,
} from "@/modules/developer-mode";
import { automationService } from "@/modules/automations";
import {
  eventDeliveryService,
  integrationEventService,
} from "@/modules/events";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const event = (await parseJsonBody(
      request,
      normalizedEventSchema,
      2_000_000,
    )) as NormalizedEvent;

    if (
      event.source === "core_brain" &&
      event.type === "developer.bug_detected"
    ) {
      developerBugDetectedPayloadSchema.parse(event.payload);
    }

    const result = await integrationEventService.publish(event, ["fly"]);

    if (
      event.source === "core_brain" &&
      event.type === "developer.bug_detected"
    ) {
      try {
        await developerModeService.projectBugDetected(event);
      } catch (error) {
        console.error("Developer information projection failed.", {
          eventId: event.id,
          error,
        });
      }
    }

    after(async () => {
      await Promise.all([
        eventDeliveryService.deliverEventId(result.event.eventId),
        automationService.processEvent(event),
      ]);
    });

    return apiCreated(result, requestId);
  });
}
