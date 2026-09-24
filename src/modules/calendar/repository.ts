import "server-only";

import { Prisma, type CalendarEvent } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";
import type {
  CalendarEventCreateInput,
  CalendarEventListQuery,
  CalendarEventUpdateInput,
} from "@/modules/calendar/contracts";

function buildWhere(query: CalendarEventListQuery): Prisma.CalendarEventWhereInput {
  const where: Prisma.CalendarEventWhereInput = {};

  if (query.status) {
    where.status = query.status.toUpperCase() as CalendarEvent["status"];
  }
  if (query.q) {
    where.OR = [
      { title: { contains: query.q } },
      { description: { contains: query.q } },
    ];
  }
  if (query.from || query.to) {
    where.startsAt = {
      ...(query.from ? { gte: new Date(query.from) } : {}),
      ...(query.to ? { lte: new Date(query.to) } : {}),
    };
  }

  return where;
}

function toCreateData(
  input: CalendarEventCreateInput,
): Prisma.CalendarEventCreateInput {
  return {
    title: input.title,
    description: input.description,
    startsAt: new Date(input.startsAt),
    endsAt: new Date(input.endsAt),
    allDay: input.allDay,
    timeZone: input.timeZone,
    status: input.status.toUpperCase() as CalendarEvent["status"],
    recurrenceRule: input.recurrenceRule,
    reminderAt: input.reminderAt ? new Date(input.reminderAt) : input.reminderAt,
    source: input.source,
    externalId: input.externalId,
    metadata: input.metadata as Prisma.InputJsonValue | undefined,
  };
}

function toUpdateData(
  input: CalendarEventUpdateInput,
): Prisma.CalendarEventUpdateInput {
  const data: Prisma.CalendarEventUpdateInput = {};

  if (input.title !== undefined) data.title = input.title;
  if (input.description !== undefined) data.description = input.description;
  if (input.startsAt !== undefined) data.startsAt = new Date(input.startsAt);
  if (input.endsAt !== undefined) data.endsAt = new Date(input.endsAt);
  if (input.allDay !== undefined) data.allDay = input.allDay;
  if (input.timeZone !== undefined) data.timeZone = input.timeZone;
  if (input.status !== undefined) {
    data.status = input.status.toUpperCase() as CalendarEvent["status"];
  }
  if (input.recurrenceRule !== undefined) {
    data.recurrenceRule = input.recurrenceRule;
  }
  if (input.reminderAt !== undefined) {
    data.reminderAt =
      input.reminderAt === null ? null : new Date(input.reminderAt);
  }
  if (input.source !== undefined) data.source = input.source;
  if (input.externalId !== undefined) data.externalId = input.externalId;
  if (input.metadata !== undefined) {
    data.metadata = input.metadata as Prisma.InputJsonValue;
  }

  return data;
}

export const calendarRepository = {
  async list(query: CalendarEventListQuery, page: number, limit: number) {
    const where = buildWhere(query);
    const [items, total] = await prisma.$transaction([
      prisma.calendarEvent.findMany({
        where,
        orderBy: { startsAt: "asc" },
        skip: (page - 1) * limit,
        take: limit,
      }),
      prisma.calendarEvent.count({ where }),
    ]);
    return { items, total };
  },

  findById(id: string) {
    return prisma.calendarEvent.findUnique({ where: { id } });
  },

  create(input: CalendarEventCreateInput) {
    return prisma.calendarEvent.create({ data: toCreateData(input) });
  },

  update(id: string, input: CalendarEventUpdateInput) {
    return prisma.calendarEvent.update({
      where: { id },
      data: toUpdateData(input),
    });
  },

  delete(id: string) {
    return prisma.calendarEvent.delete({ where: { id } });
  },
};
