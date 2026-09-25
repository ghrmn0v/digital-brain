import { describe, expect, it } from "vitest";
import {
  BrainContractError,
  brainUserId,
  canonicalBrainEventType,
  toBrainIngestRequest,
  toBrainSourceEvent,
  toProductEvent,
} from "@/lib/brain-client/bridge";
import type { NormalizedEvent } from "@/lib/events";

const productEvent: NormalizedEvent = {
  id: "evt-1",
  source: "linkedin",
  type: "job.discovered",
  timestamp: "2026-09-24T12:00:00.000Z",
  payload: { jobId: "job-1" },
  metadata: { schemaVersion: "1.0", correlationId: "corr-1" },
};

describe("Product -> Core Brain contract", () => {
  it("wraps the event in a canonical ingest ApiRequest", () => {
    const request = toBrainIngestRequest(productEvent, "usr_a", "req-1");
    expect(request.id).toBe("req-1");
    expect(request.method).toBe("ingest");
    expect(request.version).toBe("v1");
    expect(request.params?.event).toBeDefined();
  });

  it("maps the event type onto the Brain's canonical form", () => {
    const event = toBrainSourceEvent(productEvent, "usr_a");
    expect(event.type).toBe("source.linkedin.job_discovered");
    expect(event.user_id).toBe("usr_a");
    expect(event.occurred_at).toBe(productEvent.timestamp);
    expect(event.source).toEqual({ provider: "linkedin" });
  });

  it("keeps an already canonical type untouched", () => {
    expect(canonicalBrainEventType("source.linkedin.job_seen", "linkedin")).toBe(
      "source.linkedin.job_seen",
    );
  });

  it("maps the correlation id to the Brain's top-level field", () => {
    const event = toBrainSourceEvent(productEvent, "usr_a");
    expect(event.correlation_id).toBe("corr-1");
  });

  it("does not forward Product metadata the Brain would reject", () => {
    const event = toBrainSourceEvent(productEvent, "usr_a") as unknown as Record<string, unknown>;
    expect(event["metadata"]).toBeUndefined();
    expect(Object.keys(event).sort()).toEqual(
      [
        "correlation_id",
        "id",
        "occurred_at",
        "payload",
        "source",
        "timestamp",
        "type",
        "user_id",
      ].sort(),
    );
  });

  it("omits the correlation id when Product has none", () => {
    const event = toBrainSourceEvent(
      { ...productEvent, metadata: { schemaVersion: "1.0" } },
      "usr_a",
    );
    expect(event.correlation_id ?? null).toBeNull();
  });

  it("requires an explicit brain user id", () => {
    const previous = process.env.CORE_BRAIN_USER_ID;
    delete process.env.CORE_BRAIN_USER_ID;
    try {
      expect(() => brainUserId()).toThrow(BrainContractError);
      expect(() => brainUserId()).toThrow(/CORE_BRAIN_USER_ID/);
    } finally {
      if (previous !== undefined) process.env.CORE_BRAIN_USER_ID = previous;
    }
  });

  it("returns the configured user id when present", () => {
    const previous = process.env.CORE_BRAIN_USER_ID;
    process.env.CORE_BRAIN_USER_ID = " usr_demo ";
    try {
      expect(brainUserId()).toBe("usr_demo");
    } finally {
      if (previous === undefined) delete process.env.CORE_BRAIN_USER_ID;
      else process.env.CORE_BRAIN_USER_ID = previous;
    }
  });
});

describe("Core Brain -> Product contract", () => {
  it("accepts a canonical BrainEvent", () => {
    const event = toProductEvent({
      id: "evt_brain_1",
      type: "developer.bug_detected",
      timestamp: "2026-09-25T12:00:00.000Z",
      user_id: "usr_a",
      source: { provider: "core", component: "brain-events", version: null },
      payload: {
        repository: "digital-brain",
        file: "src/auth/login.ts",
        line: 42,
        title: "Possible null reference",
        message: "user may be undefined",
        severity: "warning",
        confidence: 0.7,
        correlation_id: "corr-9",
      },
      related_ids: ["bf_1"],
      version: "v1",
    });
    expect(event.id).toBe("evt_brain_1");
    expect(event.type).toBe("developer.bug_detected");
    expect(event.source).toBe("core_brain");
    expect(event.payload["repository"]).toBe("digital-brain");
    expect(event.payload["title"]).toBe("Possible null reference");
    expect(event.metadata?.correlationId).toBe("corr-9");
  });

  it("falls back to `other` for a provider Product does not know", () => {
    const event = toProductEvent({
      id: "evt_brain_2",
      type: "memory.created",
      timestamp: "2026-09-25T12:00:00.000Z",
      user_id: "usr_a",
      source: { provider: "some-unknown-provider" },
      payload: {},
    });
    expect(event.source).toBe("other");
  });

  it("rejects a payload that is neither contract", () => {
    expect(() => toProductEvent({ nonsense: true })).toThrow(BrainContractError);
    expect(() => toProductEvent(null)).toThrow(BrainContractError);
    expect(() => toProductEvent("text")).toThrow(BrainContractError);
  });
});
