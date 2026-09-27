import "server-only";

import { prisma } from "@/lib/prisma";
import type {
  TimelineItemDto,
  TimelineKind,
} from "@/modules/timeline/contracts";

export const timelineService = {
  async list(kind?: TimelineKind, limit = 100): Promise<TimelineItemDto[]> {
    const perKind = Math.max(1, Math.ceil(limit / 3));
    const include = (value: TimelineKind) => !kind || kind === value;

    const [tasks, events, jobs, actions, integrationEvents] = await Promise.all([
      include("task")
        ? prisma.task.findMany({
            orderBy: { updatedAt: "desc" },
            take: perKind,
          })
        : [],
      include("calendar")
        ? prisma.calendarEvent.findMany({
            orderBy: { startsAt: "desc" },
            take: perKind,
          })
        : [],
      include("job")
        ? prisma.job.findMany({
            orderBy: { lastSeenAt: "desc" },
            take: perKind,
          })
        : [],
      include("action")
        ? prisma.actionExecution.findMany({
            orderBy: { requestedAt: "desc" },
            take: perKind,
          })
        : [],
      include("event")
        ? prisma.integrationEvent.findMany({
            orderBy: { createdAt: "desc" },
            take: perKind,
          })
        : [],
    ]);

    return [
      ...tasks.map((task) => ({
        id: `task:${task.id}`,
        kind: "task" as const,
        title: task.title,
        description: task.description,
        occurredAt: (task.completedAt ?? task.updatedAt).toISOString(),
        status: task.status.toLowerCase(),
        href: `/tasks/${task.id}`,
        metadata: { priority: task.priority.toLowerCase(), source: task.source },
      })),
      ...events.map((event) => ({
        id: `calendar:${event.id}`,
        kind: "calendar" as const,
        title: event.title,
        description: event.description,
        occurredAt: event.startsAt.toISOString(),
        status: event.status.toLowerCase(),
        href: `/calendar/${event.id}`,
        metadata: { allDay: event.allDay, source: event.source },
      })),
      ...jobs.map((job) => ({
        id: `job:${job.id}`,
        kind: "job" as const,
        title: `${job.title} — ${job.company}`,
        description: job.location,
        occurredAt: job.firstSeenAt.toISOString(),
        status: job.status.toLowerCase(),
        href: `/jobs/${job.id}`,
        metadata: {
          source: job.source.toLowerCase(),
          url: job.url,
          relevanceReason: job.relevanceReason,
        },
      })),
      ...actions.map((action) => ({
        id: `action:${action.id}`,
        kind: "action" as const,
        title: action.action,
        description: action.error,
        occurredAt: action.requestedAt.toISOString(),
        status: action.status.toLowerCase(),
        href: "/approvals",
        metadata: { source: action.source, permissionLevel: action.permissionLevel },
      })),
      ...integrationEvents.map((event) => ({
        id: `event:${event.id}`,
        kind: "event" as const,
        title: event.type,
        description: null,
        occurredAt: event.timestamp.toISOString(),
        status: "received",
        href: null,
        metadata: { eventId: event.eventId, source: event.source },
      })),
    ]
      .sort((left, right) =>
        right.occurredAt.localeCompare(left.occurredAt),
      )
      .slice(0, limit);
  },
};
