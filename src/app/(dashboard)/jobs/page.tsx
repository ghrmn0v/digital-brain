import type { Metadata } from "next";
import Link from "next/link";
import {
  BarChart3,
  BriefcaseBusiness,
  Filter,
  RotateCcw,
} from "lucide-react";
import { JobsManager } from "@/components/jobs-manager";
import {
  EmptyState,
  InlineNotice,
  MetricCard,
  PageHeader,
  Panel,
  SectionHeading,
  inputClassName,
  secondaryButtonClassName,
  selectClassName,
} from "@/components/ui";
import { formatDateTime, formatRelativeTime } from "@/lib/client/format";
import { jobListQuerySchema, jobService } from "@/modules/jobs";

export const metadata: Metadata = { title: "Jobs" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function JobsPage({ searchParams }: PageProps<"/jobs">) {
  const params = await searchParams;
  const parsedQuery = jobListQuerySchema.safeParse({
    q: first(params.q) || undefined,
    source: first(params.source) || undefined,
    status: first(params.status) || undefined,
  });
  const query = parsedQuery.success ? parsedQuery.data : {};
  const now = new Date();

  const [result, report] = await Promise.all([
    jobService.list(query, 1, 100),
    jobService.report(),
  ]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Opportunity inbox"
        title="Jobs"
        description="AI and connectors discover and ingest jobs; Core Brain supplies relevance intelligence. This page shows the resulting product state and user workflow."
      />

      <InlineNotice>
        LinkedIn ingestion normalizes and stores jobs but never decides
        relevance. Any explanation shown here comes from Core Brain; user
        actions still pass through Product permissions.
      </InlineNotice>

      <section aria-label="Daily job report" className="grid gap-4 lg:grid-cols-[0.75fr_1.25fr]">
        <MetricCard
          label="Last 24 hours"
          value={report.total}
          detail={`Discovered between ${formatDateTime(report.period.from)} and ${formatDateTime(report.period.to)}`}
          icon={BarChart3}
          href="/jobs"
        />
        <Panel>
          <SectionHeading
            title="Daily report summary"
            description="Freshest records included in the rolling 24-hour report"
          />
          {report.jobs.length > 0 ? (
            <ul className="divide-y divide-slate-800/80">
              {report.jobs.slice(0, 3).map((job) => (
                <li key={job.id} className="flex items-center gap-3 px-5 py-3.5">
                  <BriefcaseBusiness aria-hidden="true" className="h-4 w-4 shrink-0 text-slate-500" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-200">
                      {job.title} · {job.company}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      First seen {formatRelativeTime(job.firstSeenAt, now)}
                    </p>
                  </div>
                  <span className="text-xs text-slate-500">{job.source}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={BarChart3}
              title="No jobs discovered in 24 hours"
              description="The report is based on the local firstSeenAt timestamp, not an external estimate."
            />
          )}
        </Panel>
      </section>

      <Panel>
        <form
          action="/jobs"
          method="get"
          className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-[minmax(14rem,1fr)_11rem_11rem_auto] lg:items-end"
        >
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Search</span>
            <input
              type="search"
              name="q"
              defaultValue={query.q ?? ""}
              maxLength={100}
              placeholder="Title, company, or location"
              className={inputClassName}
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Source</span>
            <select name="source" defaultValue={query.source ?? ""} className={selectClassName}>
              <option value="">All sources</option>
              <option value="linkedin">LinkedIn</option>
              <option value="manual">Manual</option>
              <option value="core_brain">Core Brain</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Status</span>
            <select name="status" defaultValue={query.status ?? ""} className={selectClassName}>
              <option value="">All statuses</option>
              <option value="seen">Seen</option>
              <option value="saved">Saved</option>
              <option value="ignored">Ignored</option>
              <option value="applied">Applied</option>
              <option value="archived">Archived</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={secondaryButtonClassName}>
              <Filter aria-hidden="true" className="h-4 w-4" />
              Apply
            </button>
            <Link href="/jobs" className={secondaryButtonClassName}>
              <RotateCcw aria-hidden="true" className="h-4 w-4" />
              Clear
            </Link>
          </div>
        </form>
      </Panel>

      <JobsManager jobs={result.items} />
    </div>
  );
}
