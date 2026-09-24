import { after, NextRequest } from "next/server";
import { authorizeRequest } from "@/lib/api/auth";
import { parseJsonBody } from "@/lib/api/request";
import { apiData, withApiErrors } from "@/lib/api/response";
import type { NormalizedEvent } from "@/lib/events";
import { automationService } from "@/modules/automations";
import {
  connectorService,
  linkedInConnector,
  linkedInJobsIngestionSchema,
} from "@/modules/connectors";
import {
  eventDeliveryService,
  integrationEventService,
  type IntegrationEventDto,
} from "@/modules/events";
import { jobService, type JobDto } from "@/modules/jobs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return withApiErrors(request, async (requestId) => {
    authorizeRequest(request);
    const input = await parseJsonBody(request, linkedInJobsIngestionSchema, 5_000_000);
    const results: Array<{
      job: JobDto;
      created: boolean;
      duplicateEvent: boolean;
      event: IntegrationEventDto;
    }> = [];
    const normalizedEvents: NormalizedEvent[] = [];

    for (const rawJob of input.jobs) {
      const ingested = await jobService.ingest({
        ...rawJob,
        source: "linkedin",
        status: "seen",
      });
      const event = linkedInConnector.normalize(rawJob);
      event.payload.jobId = ingested.job.id;
      const published = await integrationEventService.publish(event, [
        "core_brain",
        "fly",
      ]);
      normalizedEvents.push(event);
      results.push({
        ...ingested,
        duplicateEvent: published.duplicate,
        event: published.event,
      });
    }

    after(async () => {
      await Promise.all(
        results.flatMap((result, index) => [
          eventDeliveryService.deliverEventId(result.event.eventId),
          ...(result.duplicateEvent
            ? []
            : [automationService.processEvent(normalizedEvents[index])]),
        ]),
      );
    });

    await connectorService.recordHealth(
      "linkedin",
      "healthy",
      new Date(),
      null,
    );
    return apiData({ items: results }, requestId);
  });
}
