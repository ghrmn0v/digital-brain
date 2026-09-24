import { describe, expect, it } from "vitest";
import {
  getNextOccurrence,
  isValidRecurrenceRule,
} from "@/lib/domain/recurrence";

 describe("recurrence rules", () => {
  it("accepts supported frequencies and intervals", () => {
    expect(isValidRecurrenceRule("FREQ=DAILY")).toBe(true);
    expect(isValidRecurrenceRule("FREQ=WEEKLY;INTERVAL=2")).toBe(true);
    expect(isValidRecurrenceRule("FREQ=HOURLY")).toBe(false);
  });

  it("calculates the next UTC occurrence", () => {
    const next = getNextOccurrence(
      new Date("2026-01-15T10:00:00.000Z"),
      "FREQ=WEEKLY;INTERVAL=2",
    );
    expect(next.toISOString()).toBe("2026-01-29T10:00:00.000Z");
  });
});
