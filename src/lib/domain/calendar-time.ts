const datePattern = /^(\d{4})-(\d{2})-(\d{2})$/;
const timePattern = /^(\d{2}):(\d{2})$/;

export function parseLocalDate(value: string): Date {
  const match = datePattern.exec(value);
  if (!match) throw new Error("Invalid calendar date.");

  const [, year, month, day] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (
    date.getFullYear() !== Number(year) ||
    date.getMonth() !== Number(month) - 1 ||
    date.getDate() !== Number(day)
  ) {
    throw new Error("Invalid calendar date.");
  }
  return date;
}

export function parseLocalDateTime(date: string, time: string): Date {
  const timeMatch = timePattern.exec(time);
  if (!timeMatch) throw new Error("Invalid calendar time.");

  const parsedDate = parseLocalDate(date);
  const hours = Number(timeMatch[1]);
  const minutes = Number(timeMatch[2]);
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    throw new Error("Invalid calendar time.");
  }

  return new Date(
    parsedDate.getFullYear(),
    parsedDate.getMonth(),
    parsedDate.getDate(),
    hours,
    minutes,
    0,
    0,
  );
}

export function addDuration(start: Date, minutes: number): Date {
  if (!Number.isFinite(minutes) || minutes <= 0) {
    throw new Error("Event duration must be greater than zero.");
  }
  return new Date(start.getTime() + minutes * 60_000);
}

export function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function toTimeInputValue(date: Date): string {
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
}
