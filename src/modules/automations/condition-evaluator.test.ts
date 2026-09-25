import { describe, expect, it } from "vitest";
import {
  evaluateConditions,
  getValueAtPath,
} from "@/modules/automations/condition-evaluator";

describe("automation condition evaluator", () => {
  const event = {
    event: {
      type: "job.discovered",
      payload: {
        company: "Acme",
        salaryMin: 1000,
        skills: ["TypeScript", "SQL"],
      },
    },
  };

  it("reads safe nested paths", () => {
    expect(getValueAtPath(event, "event.payload.company")).toBe("Acme");
    expect(getValueAtPath(event, "event.payload.__proto__.polluted")).toBeUndefined();
  });

  it("evaluates all conditions with AND semantics", () => {
    expect(
      evaluateConditions(event, [
        { path: "event.type", operator: "eq", value: "job.discovered" },
        { path: "event.payload.salaryMin", operator: "gte", value: 1000 },
        {
          path: "event.payload.skills",
          operator: "contains",
          value: "SQL",
        },
      ]),
    ).toBe(true);
  });
});
