const dateFormatter = new Intl.DateTimeFormat("en-US", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
});

const relativeFormatter = new Intl.RelativeTimeFormat("en", {
  numeric: "auto",
});

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? dateFormatter.format(date) : "—";
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? dateTimeFormatter.format(date) : "—";
}

export function formatTime(value: string | null | undefined): string {
  const date = parseDate(value);
  return date ? timeFormatter.format(date) : "—";
}

export function formatRelativeTime(
  value: string | null | undefined,
  now = new Date(),
): string {
  const date = parseDate(value);
  if (!date) return "No timestamp";

  const differenceSeconds = Math.round((date.getTime() - now.getTime()) / 1_000);
  const absoluteSeconds = Math.abs(differenceSeconds);

  if (absoluteSeconds < 60) return "just now";
  if (absoluteSeconds < 3_600) {
    return relativeFormatter.format(Math.round(differenceSeconds / 60), "minute");
  }
  if (absoluteSeconds < 86_400) {
    return relativeFormatter.format(Math.round(differenceSeconds / 3_600), "hour");
  }
  if (absoluteSeconds < 604_800) {
    return relativeFormatter.format(Math.round(differenceSeconds / 86_400), "day");
  }
  if (absoluteSeconds < 2_592_000) {
    return relativeFormatter.format(
      Math.round(differenceSeconds / 604_800),
      "week",
    );
  }
  return formatDate(value);
}

export function toDateTimeLocalValue(value: string | null): string {
  const date = parseDate(value);
  if (!date) return "";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function toDateInputValue(value: string | null | undefined): string {
  const date = parseDate(value);
  if (!date) return "";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function combineDateAndTime(date: string, time: string): Date {
  return new Date(`${date}T${time}:00`);
}

export function humanizeToken(value: string): string {
  return value
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
