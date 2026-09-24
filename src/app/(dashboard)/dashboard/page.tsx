import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarClock,
  CheckCheck,
  CircleAlert,
  ListTodo,
  PlugZap,
  Sparkles,
} from "lucide-react";
import { AiOperationsPanel } from "@/components/ai-operations-panel";
import {
  Badge,
  EmptyState,
  MetricCard,
  PageHeader,
  Panel,
  SectionHeading,
  StatusBadge,
  cn,
} from "@/components/ui";
import {
  formatDateTime,
  formatRelativeTime,
} from "@/lib/client/format";
import { actionService } from "@/modules/actions";
import { automationService } from "@/modules/automations";
import { calendarService } from "@/modules/calendar";
import { connectorService } from "@/modules/connectors";
import { jobService } from "@/modules/jobs";
import { permissionService } from "@/modules/permissions";
import { taskService } from "@/modules/tasks";

export const metadata: Metadata = { title: "Dashboard" };

const priorityRank = { urgent: 0, high: 1, medium: 2, low: 3 } as const;

export default async function DashboardPage() {
  const now = new Date();
  const nowIso = now.toISOString();
  const [
    todo,
    inProgress,
    blocked,
    urgent,
    confirmedUpcoming,
    tentativeUpcoming,
    jobs,
    recentJobs,
    approvals,
    connectors,
    automations,
    permissions,
    taskSnapshot,
  ] = await Promise.all([
    taskService.list({ status: "todo" }, 1, 1),
    taskService.list({ status: "in_progress" }, 1, 1),
    taskService.list({ status: "blocked" }, 1, 1),
    taskService.list({ priority: "urgent" }, 1, 1),
    calendarService.list({ from: nowIso, status: "confirmed" }, 1, 6),
    calendarService.list({ from: nowIso, status: "tentative" }, 1, 6),
    jobService.list({}, 1, 1),
    jobService.list({}, 1, 5),
    actionService.list({ status: "pending_approval" }, 1, 5),
    connectorService.list(),
    automationService.list({ enabled: "true" }),
    permissionService.list({}),
    taskService.list({}, 1, 100),
  ]);

  const upcoming = {
    items: [...confirmedUpcoming.items, ...tentativeUpcoming.items]
      .sort((left, right) => left.startsAt.localeCompare(right.startsAt))
      .slice(0, 6),
    total:
      confirmedUpcoming.pagination.total + tentativeUpcoming.pagination.total,
  };

  const activeTaskCount =
    todo.pagination.total +
    inProgress.pagination.total +
    blocked.pagination.total;
  const enabledConnectors = connectors.filter((connector) => connector.enabled).length;
  const enabledPermissions = permissions.filter((permission) => permission.enabled);
  const permissionSummary = {
    automatic: enabledPermissions.filter((permission) => permission.level === "AUTOMATIC").length,
    askFirst: enabledPermissions.filter((permission) => permission.level === "ASK_FIRST").length,
    off: enabledPermissions.filter((permission) => permission.level === "OFF").length,
  };
  const coreBrainConfigured = Boolean(process.env.CORE_BRAIN_URL?.trim());
  const attentionTasks = taskSnapshot.items
    .filter(
      (task) =>
        task.status !== "done" &&
        task.status !== "cancelled" &&
        (task.status === "blocked" ||
          task.priority === "urgent" ||
          task.priority === "high" ||
          (task.dueAt !== null && new Date(task.dueAt) <= now)),
    )
    .sort((left, right) => {
      const priorityDifference =
        priorityRank[left.priority] - priorityRank[right.priority];
      if (priorityDifference !== 0) return priorityDifference;

      const leftDue = left.dueAt ? new Date(left.dueAt).getTime() : Number.MAX_SAFE_INTEGER;
      const rightDue = right.dueAt ? new Date(right.dueAt).getTime() : Number.MAX_SAFE_INTEGER;
      return leftDue - rightDue;
    })
    .slice(0, 6);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Product overview"
        title="Good focus starts with a clear system"
        description="AI requests flow through permissions and action execution. This view shows what the system completed, what needs approval, and which local integrations are active."
        actions={
          <>
            <Link
              href="/tasks?status=todo"
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
            >
              <ListTodo aria-hidden="true" className="h-4 w-4" />
              Review tasks
            </Link>
            <Link
              href="/approvals"
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
            >
              <CheckCheck aria-hidden="true" className="h-4 w-4" />
              Review approvals
            </Link>
          </>
        }
      />

      <AiOperationsPanel
        coreBrainConfigured={coreBrainConfigured}
        pendingApprovals={approvals.pagination.total}
        enabledAutomations={automations.length}
        permissionSummary={permissionSummary}
      />

      <section aria-label="Database totals" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="Active tasks"
          value={activeTaskCount}
          detail={`${todo.pagination.total} todo · ${inProgress.pagination.total} in progress`}
          icon={ListTodo}
          href="/tasks"
        />
        <MetricCard
          label="Urgent"
          value={urgent.pagination.total}
          detail={`${blocked.pagination.total} blocked tasks need review`}
          icon={CircleAlert}
          href="/tasks?priority=urgent"
        />
        <MetricCard
          label="Upcoming"
          value={upcoming.total}
          detail="Calendar events from this moment forward"
          icon={CalendarClock}
          href="/calendar"
        />
        <MetricCard
          label="Jobs tracked"
          value={jobs.pagination.total}
          detail="Local records across every source"
          icon={BriefcaseBusiness}
          href="/jobs"
        />
        <MetricCard
          label="Approvals"
          value={approvals.pagination.total}
          detail="Actions waiting for an explicit decision"
          icon={CheckCheck}
          href="/approvals"
        />
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel>
          <SectionHeading
            title="Needs attention"
            description="Blocked, urgent, high-priority, or overdue open tasks"
            action={
              <Link
                href="/tasks"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                All tasks
                <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
              </Link>
            }
          />
          {attentionTasks.length > 0 ? (
            <ul className="divide-y divide-slate-800/80">
              {attentionTasks.map((task) => {
                const overdue = task.dueAt !== null && new Date(task.dueAt) < now;
                return (
                  <li key={task.id} className="px-5 py-4">
                    <div className="flex items-start gap-3">
                      <span
                        aria-hidden="true"
                        className={cn(
                          "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                          overdue ? "bg-rose-300" : "bg-amber-300",
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="min-w-0 break-words text-sm font-medium text-slate-200">
                            {task.title}
                          </h3>
                          <StatusBadge status={overdue ? "overdue" : task.priority} />
                        </div>
                        <p className="mt-1.5 text-xs text-slate-500">
                          {task.dueAt ? (
                            <time
                              dateTime={task.dueAt}
                              title={formatDateTime(task.dueAt)}
                            >
                              Due {formatRelativeTime(task.dueAt, now)}
                            </time>
                          ) : (
                            "No due date"
                          )}
                          <span aria-hidden="true"> · </span>
                          {task.source}
                        </p>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState
              icon={Sparkles}
              title="Nothing needs immediate attention"
              description="No open task is blocked, urgent, high priority, or overdue in the current snapshot."
            />
          )}
        </Panel>

        <Panel>
          <SectionHeading
            title="Upcoming calendar"
            description="The next events on your local calendar"
            action={
              <Link
                href="/calendar"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                Open calendar
                <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
              </Link>
            }
          />
          {upcoming.items.length > 0 ? (
            <ul className="divide-y divide-slate-800/80">
              {upcoming.items.map((event) => (
                <li key={event.id} className="flex items-start gap-3 px-5 py-4">
                  <div className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-xl border border-slate-700 bg-slate-800/70 text-cyan-200">
                    <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">
                      {new Intl.DateTimeFormat("en-US", { month: "short" }).format(
                        new Date(event.startsAt),
                      )}
                    </span>
                    <span className="text-xs font-semibold">
                      {new Intl.DateTimeFormat("en-US", { day: "2-digit" }).format(
                        new Date(event.startsAt),
                      )}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="break-words text-sm font-medium text-slate-200">
                      {event.title}
                    </h3>
                    <p className="mt-1 text-xs text-slate-500">
                      <time dateTime={event.startsAt} title={formatDateTime(event.startsAt)}>
                        {formatDateTime(event.startsAt)}
                      </time>
                      {event.allDay ? " · All day" : ` – ${formatDateTime(event.endsAt).split(", ").at(-1)}`}
                    </p>
                  </div>
                  <StatusBadge status={event.status} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={CalendarClock}
              title="No upcoming events"
              description="Your calendar has no confirmed or tentative event starting from now."
              action={
                <Link href="/calendar" className="text-sm font-semibold text-cyan-300 hover:text-cyan-200">
                  Add an event
                </Link>
              }
            />
          )}
        </Panel>

        <Panel>
          <SectionHeading
            title="Recent jobs"
            description="Freshest records from configured job sources"
            action={
              <Link
                href="/jobs"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                Job inbox
                <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
              </Link>
            }
          />
          {recentJobs.items.length > 0 ? (
            <ul className="divide-y divide-slate-800/80">
              {recentJobs.items.map((job) => (
                <li key={job.id} className="flex items-center gap-3 px-5 py-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-700 bg-slate-800/70 text-slate-400">
                    <BriefcaseBusiness aria-hidden="true" className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-medium text-slate-200">{job.title}</h3>
                    <p className="mt-1 truncate text-xs text-slate-500">
                      {job.company}
                      {job.location ? ` · ${job.location}` : ""}
                    </p>
                  </div>
                  <StatusBadge status={job.status} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={BriefcaseBusiness}
              title="No jobs received yet"
              description="Jobs will appear here when a connector or manual source records them."
            />
          )}
        </Panel>

        <Panel>
          <SectionHeading
            title="Pending approvals"
            description="External actions held by ASK_FIRST policy"
            action={
              <Link
                href="/approvals"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                Decision queue
                <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
              </Link>
            }
          />
          {approvals.items.length > 0 ? (
            <ul className="divide-y divide-slate-800/80">
              {approvals.items.map((action) => (
                <li key={action.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="break-words font-mono text-sm font-semibold text-cyan-200">
                        {action.action}
                      </h3>
                      <p className="mt-1.5 text-xs text-slate-500">
                        {action.source} · requested {formatRelativeTime(action.requestedAt, now)}
                      </p>
                    </div>
                    <Badge tone="warning" dot>
                      Pending
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={CheckCheck}
              title="Approval queue is clear"
              description="No action is waiting for a human decision."
            />
          )}
        </Panel>
      </div>

      <Panel>
        <SectionHeading
          title="Connector state"
          description="Only operational health and enablement are shown; credentials never enter this view"
          action={
            <Link
              href="/connectors"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
            >
              Manage connectors
              <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
            </Link>
          }
        />
        {connectors.length > 0 ? (
          <div className="grid gap-px bg-slate-800 sm:grid-cols-2 xl:grid-cols-3">
            {connectors.map((connector) => (
              <div key={connector.id} className="flex items-center gap-3 bg-slate-900/70 px-5 py-4">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 text-slate-400">
                  <PlugZap aria-hidden="true" className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200">{connector.name}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {connector.lastSyncAt
                      ? `Synced ${formatRelativeTime(connector.lastSyncAt, now)}`
                      : "No sync recorded"}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <StatusBadge status={connector.status} />
                  {!connector.enabled ? <span className="text-[10px] text-slate-600">Disabled</span> : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={PlugZap}
            title="No connectors seeded"
            description="The local database currently contains no connector records."
          />
        )}
        <div className="flex items-center gap-2 border-t border-slate-800/80 px-5 py-3 text-xs text-slate-500">
          <span className="font-semibold text-slate-400">{enabledConnectors}</span>
          of {connectors.length} connectors enabled
        </div>
      </Panel>
    </div>
  );
}
