import type { Metadata } from "next";
import Link from "next/link";
import { Filter, RotateCcw } from "lucide-react";
import { TasksManager } from "@/components/tasks-manager";
import {
  InlineNotice,
  PageHeader,
  Panel,
  inputClassName,
  secondaryButtonClassName,
  selectClassName,
} from "@/components/ui";
import { taskListQuerySchema, taskService } from "@/modules/tasks";

export const metadata: Metadata = { title: "Tasks" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function TasksPage({ searchParams }: PageProps<"/tasks">) {
  const params = await searchParams;
  const parsedQuery = taskListQuerySchema.safeParse({
    q: first(params.q) || undefined,
    status: first(params.status) || undefined,
    priority: first(params.priority) || undefined,
  });
  const query = parsedQuery.success ? parsedQuery.data : {};
  const result = await taskService.list(query, 1, 100);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Execution"
        title="Tasks"
        description="AI-managed execution state. Core Brain and automations create or update tasks through the permission-aware action API; manual controls are the fallback."
      />

      <InlineNotice>
        AI does not need to use the task form. It sends actions such as
        <code className="mx-1 font-mono text-cyan-100">tasks.create_task</code>;
        Product applies AUTOMATIC, ASK_FIRST, or OFF policy before writing.
      </InlineNotice>

      <Panel>
        <form
          action="/tasks"
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
              placeholder="Title or description"
              className={inputClassName}
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Status</span>
            <select name="status" defaultValue={query.status ?? ""} className={selectClassName}>
              <option value="">All statuses</option>
              <option value="todo">Todo</option>
              <option value="in_progress">In progress</option>
              <option value="blocked">Blocked</option>
              <option value="done">Done</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Priority</span>
            <select name="priority" defaultValue={query.priority ?? ""} className={selectClassName}>
              <option value="">All priorities</option>
              <option value="urgent">Urgent</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="submit" className={secondaryButtonClassName}>
              <Filter aria-hidden="true" className="h-4 w-4" />
              Apply
            </button>
            <Link href="/tasks" className={secondaryButtonClassName}>
              <RotateCcw aria-hidden="true" className="h-4 w-4" />
              Clear
            </Link>
          </div>
        </form>
      </Panel>

      <TasksManager tasks={result.items} total={result.pagination.total} />
    </div>
  );
}
