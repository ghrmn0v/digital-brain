import { z } from "zod";

export const TIMELINE_KINDS = [
  "task",
  "calendar",
  "job",
  "action",
  "event",
] as const;

export const timelineQuerySchema = z.object({
  kind: z.enum(TIMELINE_KINDS).optional(),
  limit: z.coerce.number().int().min(1).max(200).default(100),
});

export type TimelineKind = (typeof TIMELINE_KINDS)[number];

export interface TimelineItemDto {
  id: string;
  kind: TimelineKind;
  title: string;
  description: string | null;
  occurredAt: string;
  status: string;
  href: string | null;
  metadata: Record<string, unknown>;
}
