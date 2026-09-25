import "server-only";

import type { CalendarEvent } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import type { JsonValue } from "@/lib/events";
import type {
  CalendarEventCreateInput,
  CalendarEventDto,
  CalendarEventListQuery,
  CalendarEventStatus,
  CalendarEventUpdateInput,
} from "@/modules/calendar/contracts";
import { calendarRepository } from "@/modules/calendar/repository";

function toCalendarEventDto(event: CalendarEvent): CalendarEventDto {
  return {
    id: event.id,
    title: event.title,
    description: event.description,
    startsAt: event.startsAt.toISOString(),
    endsAt: event.endsAt.toISOString(),
    allDay: event.allDay,
    timeZone: event.timeZone,
    status: event.status.toLowerCase() as CalendarEventStatus,
    recurrenceRule: event.recurrenceRule,
    reminderAt: event.reminderAt?.toISOString() ?? null,
    source: event.source,
    externalId: event.externalId,
    metadata: (event.metadata as JsonValue | null) ?? null,
    createdAt: event.createdAt.toISOString(),
    updatedAt: event.updatedAt.toISOString(),
  };
}

function assertFound(event: CalendarEvent | null): asserts event is CalendarEvent {
  if (!event) {
    throw new ApiError(404, "CALENDAR_EVENT_NOT_FOUND", "Calendar event not found.");
  }
}

function assertValidTimes(startsAt: Date, endsAt: Date, reminderAt: Date | null) {
  if (endsAt <= startsAt) {
    throw new ApiError(
      400,
      "INVALID_EVENT_TIME_RANGE",
      "endsAt must be later than startsAt.",
    );
  }
  if (reminderAt && reminderAt > startsAt) {
    throw new ApiError(
      400,
      "INVALID_EVENT_REMINDER",
      "reminderAt cannot be later than startsAt.",
    );
  }
}

export const calendarService = {
  async list(query: CalendarEventListQuery, page: number, limit: number) {
    if (query.from && query.to && new Date(query.from) >= new Date(query.to)) {
      throw new ApiError(
        400,
        "INVALID_DATE_RANGE",
        "The from date must be earlier than the to date.",
      );
    }

    const { items, total } = await calendarRepository.list(query, page, limit);
    return {
      items: items.map(toCalendarEventDto),
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    };
  },

  async get(id: string) {
    const event = await calendarRepository.findById(id);
    assertFound(event);
    return toCalendarEventDto(event);
  },

  async create(input: CalendarEventCreateInput) {
    const normalized: CalendarEventCreateInput = {
      ...input,
      description: input.description ?? null,
      timeZone: input.timeZone ?? null,
      recurrenceRule: input.recurrenceRule ?? null,
      reminderAt: input.reminderAt ?? null,
      externalId: input.externalId ?? null,
    };
    return toCalendarEventDto(await calendarRepository.create(normalized));
  },

  async update(id: string, input: CalendarEventUpdateInput) {
    const current = await calendarRepository.findById(id);
    assertFound(current);

    const startsAt = input.startsAt ? new Date(input.startsAt) : current.startsAt;
    const endsAt = input.endsAt ? new Date(input.endsAt) : current.endsAt;
    const reminderAt =
      input.reminderAt === undefined
        ? current.reminderAt
        : input.reminderAt === null
          ? null
          : new Date(input.reminderAt);
    assertValidTimes(startsAt, endsAt, reminderAt);

    return toCalendarEventDto(await calendarRepository.update(id, input));
  },

  async remove(id: string) {
    const current = await calendarRepository.findById(id);
    assertFound(current);
    await calendarRepository.delete(id);
  },
};
