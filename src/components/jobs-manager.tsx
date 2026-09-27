"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Archive,
  Bookmark,
  BriefcaseBusiness,
  Check,
  ExternalLink,
  EyeOff,
  MapPin,
  Send,
  Sparkles,
} from "@/components/icons";
import type { JobDto, JobStatus } from "@/modules/jobs/contracts";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import { formatDate, formatDateTime } from "@/lib/client/format";
import {
  Badge,
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
  secondaryButtonClassName,
} from "@/components/ui";

const jobActions: Array<{
  status: Exclude<JobStatus, "seen">;
  label: string;
  icon: typeof Bookmark;
}> = [
  { status: "saved", label: "Save", icon: Bookmark },
  { status: "ignored", label: "Ignore", icon: EyeOff },
  { status: "applied", label: "Applied", icon: Send },
  { status: "archived", label: "Archive", icon: Archive },
];

function formatSalary(job: JobDto): string | null {
  if (job.salaryMin === null && job.salaryMax === null) return null;

  try {
    const formatter = new Intl.NumberFormat("en-US", {
      style: job.salaryCurrency ? "currency" : "decimal",
      currency: job.salaryCurrency ?? undefined,
      maximumFractionDigits: 0,
    });
    if (job.salaryMin !== null && job.salaryMax !== null) {
      return `${formatter.format(job.salaryMin)} – ${formatter.format(job.salaryMax)}`;
    }
    return formatter.format(job.salaryMin ?? job.salaryMax ?? 0);
  } catch {
    const values = [job.salaryMin, job.salaryMax].filter(
      (value): value is number => value !== null,
    );
    return values.join(" – ");
  }
}

function JobCard({
  job,
  disabled,
  onStatus,
}: {
  job: JobDto;
  disabled: boolean;
  onStatus: (id: string, status: JobStatus) => Promise<boolean>;
}) {
  const salary = formatSalary(job);
  const relevanceReason = job.relevanceReason?.trim();

  return (
    <article className="px-5 py-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="info">{job.source}</Badge>
            <StatusBadge status={job.status} />
            {job.publishedAt ? (
              <span className="text-xs text-[var(--text-muted)]">
                Published {formatDate(job.publishedAt)}
              </span>
            ) : null}
          </div>
          <h3 className="mt-3 break-words text-base font-semibold text-[var(--text-primary)]">
            {job.title}
          </h3>
          <p className="mt-1 text-sm font-medium text-[var(--text-secondary)]">{job.company}</p>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-[var(--text-muted)]">
            {job.location ? (
              <span className="inline-flex items-center gap-1.5">
                <MapPin aria-hidden="true" className="h-3.5 w-3.5" />
                {job.location}
              </span>
            ) : null}
            {job.employmentType ? <span>{job.employmentType}</span> : null}
            {salary ? <span>{salary}</span> : null}
            <span>
              Last seen{" "}
              <time dateTime={job.lastSeenAt} title={formatDateTime(job.lastSeenAt)}>
                {formatDateTime(job.lastSeenAt)}
              </time>
            </span>
          </div>
          {job.skills.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {job.skills.slice(0, 8).map((skill) => (
                <span
                  key={skill}
                  className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)] px-2 py-1 text-[11px] text-[var(--text-secondary)]"
                >
                  {skill}
                </span>
              ))}
              {job.skills.length > 8 ? (
                <span className="px-1 py-1 text-[11px] text-[var(--text-muted)]">
                  +{job.skills.length - 8} more
                </span>
              ) : null}
            </div>
          ) : null}
          {relevanceReason ? (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-[var(--accent)]/15 bg-[var(--accent)]/[0.06] px-3 py-2.5 text-sm leading-6 text-[var(--accent)]/80">
              <Sparkles aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-[var(--accent)]" />
              <p>{relevanceReason}</p>
            </div>
          ) : null}
        </div>

        {job.url ? (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className={secondaryButtonClassName}
            aria-label={`Open ${job.title} at ${job.company} in a new tab`}
          >
            Open original
            <ExternalLink aria-hidden="true" className="h-4 w-4" />
          </a>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--panel-line)]/70 pt-4">
        {jobActions.map((action) => {
          const Icon = action.icon;
          const active = job.status === action.status;
          return (
            <button
              key={action.status}
              type="button"
              disabled={disabled || active}
              onClick={() => void onStatus(job.id, action.status)}
              className={secondaryButtonClassName}
              aria-label={`${action.label} ${job.title} at ${job.company}`}
            >
              {active ? (
                <Check aria-hidden="true" className="h-4 w-4 text-[var(--success)]" />
              ) : (
                <Icon aria-hidden="true" className="h-4 w-4" />
              )}
              {action.label}
            </button>
          );
        })}
      </div>
    </article>
  );
}

export function JobsManager({ jobs }: { jobs: JobDto[] }) {
  const router = useRouter();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function updateStatus(id: string, status: JobStatus): Promise<boolean> {
    setPendingId(id);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<JobDto>(`/api/jobs/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { status },
      });
      setSuccess(`Job marked as ${status}.`);
      router.refresh();
      return true;
    } catch (caught) {
      setError(getErrorMessage(caught, "Job status could not be updated."));
      return false;
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="space-y-5">
      {error ? <ErrorBanner title="Job request failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <Panel>
        <SectionHeading
          title="Job inbox"
          description="Review records and open the original posting"
          action={
            pendingId ? (
              <span className="inline-flex items-center gap-2 text-xs text-[var(--accent)]">
                <ButtonSpinner /> Updating
              </span>
            ) : null
          }
        />
        {jobs.length > 0 ? (
          <div className="divide-y divide-[var(--panel-line)]/80">
            {jobs.map((job) => (
              <JobCard
                key={`${job.id}:${job.status}:${job.updatedAt}`}
                job={job}
                disabled={pendingId !== null}
                onStatus={updateStatus}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={BriefcaseBusiness}
            title="No jobs match this view"
            description="No jobs match. Change a filter, or ingest a posting."
          />
        )}
      </Panel>
    </div>
  );
}
