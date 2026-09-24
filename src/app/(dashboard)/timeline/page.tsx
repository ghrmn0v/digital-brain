import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  CheckCheck,
  Filter,
  ListTodo,
  RadioTower,
  RotateCcw,
} from "lucide-react";
import {
  Badge,
  EmptyState,
  PageHeader,
  Panel,
  SectionHeading,
  StatusBadge,
  secondaryButtonClassName,
  selectClassName,
} from "@/components/ui";
import {
  formatDateTime,
  formatRelativeTime,
  humanizeToken,
} from "@/lib/client/format";
import {
  TIMELINE_KINDS,
  timelineService,
  type TimelineItemDto,
  type TimelineKind,
} from "@/modules/timeline";

export const metadata: Metadata = { title: "Timeline" };

const kindIcons = {
  task: ListTodo,
  calendar: CalendarDays,
  job: BriefcaseBusiness,
  action: CheckCheck,
  event: RadioTower,
} as const;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function internalHref(kind: TimelineKind): string | null {
  switch (kind) {
    case "task":
      return "/tasks";
    case "calendar":
      return "/calendar";
    case "job":
      return "/jobs";
    case "action":
      return "/approvals";
    case "event":
      return null;
  }
}

function safeMetadataString(
  metadata: Record<string, unknown>,
  key: string,
): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function TimelineRow({ item, now }: { item: TimelineItemDto; now: Date }) {
  const Icon = kindIcons[item.kind];
  const source = safeMetadataString(item.metadata, "source");
  const externalUrl =
    item.kind === "job" ? safeMetadataString(item.metadata, "url") : null;
  const destination = externalUrl ?? internalHref(item.kind);
  const external = Boolean(externalUrl);

  return (
    <li className="relative pl-12 sm:pl-14">
      <span className="absolute left-0 top-1 flex h-9 w-9 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-400 shadow-lg">
        <Icon aria-hidden="true" className="h-4 w-4" />
      </span>
      <div className="pb-7">
        <article className="rounded-2xl border border-slate-800/90 bg-slate-900/50 p-4 transition hover:border-slate-700 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="info">{humanizeToken(item.kind)}</Badge>
                <StatusBadge status={item.status} />
                {source ? <span className="text-xs text-slate-500">Source: {source}</span> : null}
              </div>
              <h2 className="mt-3 break-words text-sm font-semibold text-slate-100">
                {item.title}
              </h2>
              {item.description ? (
                <p className="mt-1.5 line-clamp-3 text-sm leading-6 text-slate-500">
                  {item.description}
                </p>
              ) : null}
            </div>
            {destination ? (
              external ? (
                <a
                  href={destination}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={secondaryButtonClassName}
                  aria-label={`Open ${item.title} source in a new tab`}
                >
                  Open source
                  <ArrowUpRight aria-hidden="true" className="h-4 w-4" />
                </a>
              ) : (
                <Link href={destination} className={secondaryButtonClassName}>
                  Open {item.kind}
                  <ArrowUpRight aria-hidden="true" className="h-4 w-4" />
                </Link>
              )
            ) : null}
          </div>
          <p className="mt-4 border-t border-slate-800/70 pt-3 text-xs text-slate-500">
            <time
              dateTime={item.occurredAt}
              title={formatDateTime(item.occurredAt)}
            >
              {formatDateTime(item.occurredAt)}
            </time>
            <span aria-hidden="true"> · </span>
            {formatRelativeTime(item.occurredAt, now)}
          </p>
        </article>
      </div>
    </li>
  );
}

export default async function TimelinePage({
  searchParams,
}: PageProps<"/timeline">) {
  const params = await searchParams;
  const requestedKind = first(params.kind);
  const kind = TIMELINE_KINDS.includes(
    requestedKind as (typeof TIMELINE_KINDS)[number],
  )
    ? (requestedKind as (typeof TIMELINE_KINDS)[number])
    : undefined;
  const items = await timelineService.list(kind, 150);
  const now = new Date();

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Local history"
        title="Timeline"
        description="A chronological, read-only view assembled from real task, calendar, job, action, and integration-event records."
      />

      <Panel>
        <form
          action="/timeline"
          method="get"
          className="grid gap-3 p-4 sm:grid-cols-[12rem_auto_auto] sm:items-end"
        >
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Kind</span>
            <select name="kind" defaultValue={kind ?? ""} className={selectClassName}>
              <option value="">All kinds</option>
              {TIMELINE_KINDS.map((value) => (
                <option key={value} value={value}>{humanizeToken(value)}</option>
              ))}
            </select>
          </label>
          <button type="submit" className={secondaryButtonClassName}>
            <Filter aria-hidden="true" className="h-4 w-4" />
            Apply
          </button>
          <Link href="/timeline" className={secondaryButtonClassName}>
            <RotateCcw aria-hidden="true" className="h-4 w-4" />
            Clear
          </Link>
        </form>
      </Panel>

      <Panel>
        <SectionHeading
          title="Product timeline"
          description={
            kind
              ? `${humanizeToken(kind)} records, newest first`
              : "All available local records, newest first"
          }
        />
        {items.length > 0 ? (
          <div className="px-5 py-6 sm:px-6">
            <ol className="relative before:absolute before:bottom-3 before:left-[1.12rem] before:top-3 before:w-px before:bg-slate-800">
              {items.map((item) => (
                <TimelineRow key={item.id} item={item} now={now} />
              ))}
            </ol>
          </div>
        ) : (
          <EmptyState
            icon={RadioTower}
            title={kind ? `No ${humanizeToken(kind).toLowerCase()} activity` : "No timeline activity"}
            description="The local database has no records for this view. Activity appears here as tasks, events, jobs, actions, and integration events are recorded."
          />
        )}
      </Panel>
    </div>
  );
}
