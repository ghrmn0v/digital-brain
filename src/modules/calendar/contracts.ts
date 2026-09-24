import { z } from "zod";
import { isValidRecurrenceRule } from "@/lib/domain/recurrence";
import { isValidTimeZone } from "@/lib/domain/time-zone";
import type { JsonValue } from "@/lib/events";

export const CALENDAR_EVENT_STATUSES = [
  "tentative",
  "confirmed",
  "cancelled",
] as const;

export type CalendarEventStatus = (typeof CALENDAR_EVENT_STATUSES)[number];

const optionalDate = z.iso.datetime({ offset: true }).nullable().optional();
const recurrenceRule = z
  .string()
  .max(128)
  .refine(isValidRecurrenceRule, "Use a supported RRULE value.");
const timeZone = z
  .string()
  .max(100)
  .refine(isValidTimeZone, "Use a valid IANA time zone.");

export const calendarEventCreateSchema = z
  .object({
    title: z.string().trim().min(1).max(200),
    description: z.string().trim().max(10_000).nullable().optional(),
    startsAt: z.iso.datetime({ offset: true }),
    endsAt: z.iso.datetime({ offset: true }),
    allDay: z.boolean().default(false),
    timeZone: timeZone.nullable().optional(),
    status: z.enum(CALENDAR_EVENT_STATUSES).default("confirmed"),
    recurrenceRule: recurrenceRule.nullable().optional(),
    reminderAt: optionalDate,
    source: z.string().trim().min(1).max(64).default("local"),
    externalId: z.string().trim().min(1).max(256).nullable().optional(),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict()
  .superRefine((value, context) => {
    if (new Date(value.endsAt) <= new Date(value.startsAt)) {
      context.addIssue({
        code: "custom",
        path: ["endsAt"],
        message: "endsAt must be later than startsAt.",
      });
    }
    if (
      value.reminderAt &&
      new Date(value.reminderAt) > new Date(value.startsAt)
    ) {
      context.addIssue({
        code: "custom",
        path: ["reminderAt"],
        message: "reminderAt cannot be later than startsAt.",
      });
    }
  });

export const calendarEventUpdateSchema = z
  .object({
    title: z.string().trim().min(1).max(200).optional(),
    description: z.string().trim().max(10_000).nullable().optional(),
    startsAt: z.iso.datetime({ offset: true }).optional(),
    endsAt: z.iso.datetime({ offset: true }).optional(),
    allDay: z.boolean().optional(),
    timeZone: timeZone.nullable().optional(),
    status: z.enum(CALENDAR_EVENT_STATUSES).optional(),
    recurrenceRule: recurrenceRule.nullable().optional(),
    reminderAt: optionalDate,
    source: z.string().trim().min(1).max(64).optional(),
    externalId: z.string().trim().min(1).max(256).nullable().optional(),
    metadata: z.record(z.string(), z.json()).optional(),
  })
  .strict()
  .refine((value) => Object.keys(value).length > 0, {
    message: "At least one field must be provided.",
  });

export const calendarEventListQuerySchema = z.object({
  q: z.string().trim().max(100).optional(),
  status: z.enum(CALENDAR_EVENT_STATUSES).optional(),
  from: z.iso.datetime({ offset: true }).optional(),
  to: z.iso.datetime({ offset: true }).optional(),
});

export type CalendarEventCreateInput = z.infer<
  typeof calendarEventCreateSchema
>;
export type CalendarEventUpdateInput = z.infer<
  typeof calendarEventUpdateSchema
>;
export type CalendarEventListQuery = z.infer<
  typeof calendarEventListQuerySchema
>;

export interface CalendarEventDto {
  id: string;
  title: string;
  description: string | null;
  startsAt: string;
  endsAt: string;
  allDay: boolean;
  timeZone: string | null;
  status: CalendarEventStatus;
  recurrenceRule: string | null;
  reminderAt: string | null;
  source: string;
  externalId: string | null;
  metadata: JsonValue | null;
  createdAt: string;
  updatedAt: string;
}
