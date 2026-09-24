import "server-only";

import { createHash } from "node:crypto";
import {
  BaseConnector,
  type ConnectorConfig,
  type HealthStatus,
} from "@/lib/connectors";
import type { JsonObject, NormalizedEvent } from "@/lib/events";
import { jobUpsertSchema, type JobUpsertInput } from "@/modules/jobs";

export class LinkedInConnector extends BaseConnector {
  readonly id = "linkedin";
  readonly name = "LinkedIn";
  readonly version = "1.0.0";
  private connected = false;

  async authenticate(config: ConnectorConfig): Promise<boolean> {
    const accessToken = config.credentialsRecord?.accessToken;
    this.connected = typeof accessToken === "string" && accessToken.length > 0;
    return this.connected;
  }

  async connect(): Promise<boolean> {
    return this.connected;
  }

  async disconnect(): Promise<boolean> {
    this.connected = false;
    return true;
  }

  async healthCheck(): Promise<HealthStatus> {
    return {
      status: this.connected ? "healthy" : "disconnected",
      message: this.connected
        ? undefined
        : "LinkedIn credentials have not been configured in this process.",
    };
  }

  normalize(rawData: unknown, eventType = "job.discovered"): NormalizedEvent {
    const job: JobUpsertInput = jobUpsertSchema.parse({
      ...(rawData as Record<string, unknown>),
      source: "linkedin",
    });
    const eventId = `linkedin-job-${createHash("sha256")
      .update(job.externalId)
      .digest("hex")
      .slice(0, 32)}`;

    return {
      id: eventId,
      source: "linkedin",
      type: eventType,
      timestamp: new Date().toISOString(),
      payload: {
        externalId: job.externalId,
        title: job.title,
        company: job.company,
        location: job.location ?? null,
        employmentType: job.employmentType ?? null,
        description: job.description ?? null,
        url: job.url ?? null,
        salaryMin: job.salaryMin ?? null,
        salaryMax: job.salaryMax ?? null,
        salaryCurrency: job.salaryCurrency ?? null,
        skills: job.skills ?? [],
        publishedAt: job.publishedAt ?? null,
        metadata: (job.metadata ?? {}) as JsonObject,
      },
      metadata: {
        schemaVersion: "1.0",
        connectorVersion: this.version,
        rawId: job.externalId,
      },
    };
  }
}
