import { describe, expect, it } from "vitest";
import {
  addDuration,
  parseLocalDateTime,
  toDateInputValue,
  toTimeInputValue,
} from "@/lib/domain/calendar-time";

describe("calendar local time", () => {
  it("parses start date and time without string concatenation ambiguity", () => {
    const start = parseLocalDateTime("2026-09-25", "14:30");
    expect(toDateInputValue(start)).toBe("2026-09-25");
    expect(toTimeInputValue(start)).toBe("14:30");
  });

  it("calculates the end time from an explicit duration", () => {
    const start = parseLocalDateTime("2026-09-25", "14:30");
    const end = addDuration(start, 90);
    expect(toTimeInputValue(end)).toBe("16:00");
  });

  it("rejects invalid dates and times", () => {
    expect(() => parseLocalDateTime("2026-02-30", "10:00")).toThrow();
    expect(() => parseLocalDateTime("2026-09-25", "25:00")).toThrow();
  });
});
