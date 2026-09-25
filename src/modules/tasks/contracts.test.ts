import { describe, expect, it } from "vitest";
import { taskCreateSchema } from "@/modules/tasks/contracts";

describe("task contracts", () => {
  it("normalizes defaults", () => {
    const task = taskCreateSchema.parse({ title: "Write integration contract" });
    expect(task.status).toBe("todo");
    expect(task.priority).toBe("medium");
    expect(task.source).toBe("local");
  });

  it("rejects unknown fields and invalid recurrence", () => {
    expect(() =>
      taskCreateSchema.parse({
        title: "Invalid",
        recurrenceRule: "FREQ=HOURLY",
        unexpected: true,
      }),
    ).toThrow();
  });
});
