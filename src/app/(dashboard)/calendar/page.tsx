import type { Metadata } from "next";
import Link from "next/link";
import { Filter, RotateCcw } from "lucide-react";
import { CalendarManager } from "@/components/calendar-manager";
import {
  InlineNotice,
  PageHeader,
  Panel,
  inputClassName,
  secondaryButtonClassName,
  selectClassName,
} from "@/components/ui";
import { calendarEventListQuerySchema, calendarService } from "@/modules/calendar";

export const metadata: Metadata = { title: "Calendar" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CalendarPage({
  searchParams,
}: PageProps<"/calendar">) {
  const params = await searchParams;
  const parsedQuery = calendarEventListQuerySchema.safeParse({
    q: first(params.q) || undefined,
    status: first(params.status) || undefined,
  });
  const query = parsedQuery.success ? parsedQuery.data : {};
  const result = await calendarService.list(query, 1, 100);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Schedule"
        title="Calendar"
        description="AI-managed schedule state. Core Brain requests calendar actions through Product; the user only decides actions that policy marks ASK_FIRST."
      />

      <InlineNotice>
        Calendar actions follow the same execution path as tasks. Product never
        lets an automation or connector create, update, or delete an event
        without resolving its permission first.
      </InlineNotice>

      <Panel>
        <form
          action="/calendar"
          method="get"
          className="grid gap-3 p-4 sm:grid-cols-[minmax(14rem,1fr)_12rem_auto] sm:items-end"
        >
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Search</span>
            <input
              type="search"
              name="q"
              defaultValue={query.q ?? ""}
              maxLength={100}
              placeholder="Title or description"
              className={inputClassName}
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Status</span>
            <select name="status" defaultValue={query.status ?? ""} className={selectClassName}>
              <option value="">All statuses</option>
              <option value="confirmed">Confirmed</option>
              <option value="tentative">Tentative</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={secondaryButtonClassName}>
              <Filter aria-hidden="true" className="h-4 w-4" />
              Apply
            </button>
            <Link href="/calendar" className={secondaryButtonClassName}>
              <RotateCcw aria-hidden="true" className="h-4 w-4" />
              Clear
            </Link>
          </div>
        </form>
      </Panel>

      <CalendarManager events={result.items} total={result.pagination.total} />
    </div>
  );
}
