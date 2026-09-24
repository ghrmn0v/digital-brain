const recurrencePattern =
  /^FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY)(?:;INTERVAL=([1-9]\d*))?$/i;

export function isValidRecurrenceRule(value: string): boolean {
  const match = recurrencePattern.exec(value.trim());
  if (!match) return false;
  const interval = Number(match[2] ?? "1");
  return interval >= 1 && interval <= 52;
}

export function getNextOccurrence(date: Date, rule: string): Date {
  if (!isValidRecurrenceRule(rule)) {
    throw new Error("Unsupported recurrence rule.");
  }

  const match = recurrencePattern.exec(rule.trim());
  const frequency = match?.[1]?.toUpperCase();
  const interval = Number(match?.[2] ?? "1");
  const next = new Date(date);

  switch (frequency) {
    case "DAILY":
      next.setUTCDate(next.getUTCDate() + interval);
      break;
    case "WEEKLY":
      next.setUTCDate(next.getUTCDate() + interval * 7);
      break;
    case "MONTHLY":
      next.setUTCMonth(next.getUTCMonth() + interval);
      break;
    case "YEARLY":
      next.setUTCFullYear(next.getUTCFullYear() + interval);
      break;
    default:
      throw new Error("Unsupported recurrence frequency.");
  }

  return next;
}
