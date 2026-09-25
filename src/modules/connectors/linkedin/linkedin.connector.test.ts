import { describe, expect, it } from "vitest";
import { LinkedInConnector } from "@/modules/connectors/linkedin";

describe("LinkedInConnector", () => {
  const connector = new LinkedInConnector();

  it("normalizes a validated job without adding relevance logic", () => {
    const first = connector.normalize({
      externalId: "job-123",
      title: "Senior Engineer",
      company: "Acme",
      location: "Baku",
      skills: ["TypeScript"],
    });
    const second = connector.normalize({
      externalId: "job-123",
      title: "Senior Engineer",
      company: "Acme",
      location: "Baku",
      skills: ["TypeScript"],
    });

    expect(first.id).toBe(second.id);
    expect(first.source).toBe("linkedin");
    expect(first.type).toBe("job.discovered");
    expect(first.payload.company).toBe("Acme");
    expect(first.payload).not.toHaveProperty("relevanceReason");
  });

  it("rejects malformed jobs", () => {
    expect(() =>
      connector.normalize({ externalId: "job-123", title: "Only title" }),
    ).toThrow();
  });
});
