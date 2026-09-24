"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  CalendarClock,
  ListTodo,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import type { TaskDto, TaskPriority, TaskStatus } from "@/modules/tasks/contracts";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  formatDateTime,
  toDateTimeLocalValue,
} from "@/lib/client/format";
import {
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
  dangerButtonClassName,
  inputClassName,
  primaryButtonClassName,
  secondaryButtonClassName,
  selectClassName,
} from "@/components/ui";

const statuses: Array<{ value: TaskStatus; label: string }> = [
  { value: "todo", label: "Todo" },
  { value: "in_progress", label: "In progress" },
  { value: "blocked", label: "Blocked" },
  { value: "done", label: "Done" },
  { value: "cancelled", label: "Cancelled" },
];

const priorities: Array<{ value: TaskPriority; label: string }> = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

function TaskRow({
  task,
  disabled,
  onUpdate,
  onDelete,
}: {
  task: TaskDto;
  disabled: boolean;
  onUpdate: (
    id: string,
    patch: {
      status?: TaskStatus;
      priority?: TaskPriority;
      dueAt?: string | null;
    },
    successMessage: string,
  ) => Promise<boolean>;
  onDelete: (task: TaskDto) => Promise<void>;
}) {
  const [status, setStatus] = useState<TaskStatus>(task.status);
  const [priority, setPriority] = useState<TaskPriority>(task.priority);
  const [dueAt, setDueAt] = useState(toDateTimeLocalValue(task.dueAt));
  const [rowPending, setRowPending] = useState(false);
  const rowDisabled = disabled || rowPending;

  async function updateField(
    patch: Parameters<typeof onUpdate>[1],
    successMessage: string,
    rollback?: () => void,
  ) {
    setRowPending(true);
    const succeeded = await onUpdate(task.id, patch, successMessage);
    if (!succeeded) rollback?.();
    setRowPending(false);
  }

  return (
    <article className="px-5 py-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="break-words text-sm font-semibold text-slate-100">
              {task.title}
            </h3>
            <StatusBadge status={task.status} />
            <StatusBadge status={task.priority} />
          </div>
          {task.description ? (
            <p className="mt-2 line-clamp-3 max-w-3xl text-sm leading-6 text-slate-500">
              {task.description}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <CalendarClock aria-hidden="true" className="h-3.5 w-3.5" />
              {task.dueAt ? (
                <time dateTime={task.dueAt} title={formatDateTime(task.dueAt)}>
                  {formatDateTime(task.dueAt)}
                </time>
              ) : (
                "No due date"
              )}
            </span>
            <span>Source: {task.source}</span>
            {task.recurrenceRule ? <span>Repeats: {task.recurrenceRule}</span> : null}
          </div>
        </div>

        <button
          type="button"
          disabled={rowDisabled}
          onClick={() => {
            if (!window.confirm(`Delete “${task.title}”? This cannot be undone.`)) return;
            void onDelete(task);
          }}
          className={dangerButtonClassName}
          aria-label={`Delete task ${task.title}`}
        >
          <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
          Delete
        </button>
      </div>

      <div className="mt-4 grid gap-3 border-t border-slate-800/70 pt-4 sm:grid-cols-2 xl:grid-cols-[minmax(9rem,0.65fr)_minmax(9rem,0.65fr)_minmax(15rem,1fr)_auto] xl:items-end">
        <label className="space-y-1.5 text-xs font-medium text-slate-400">
          <span>Status</span>
          <select
            value={status}
            disabled={rowDisabled}
            onChange={(event) => {
              const previous = status;
              const next = event.target.value as TaskStatus;
              setStatus(next);
              void updateField(
                { status: next },
                `Task status updated to ${next.replace("_", " ")}.`,
                () => setStatus(previous),
              );
            }}
            className={selectClassName}
          >
            {statuses.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1.5 text-xs font-medium text-slate-400">
          <span>Priority</span>
          <select
            value={priority}
            disabled={rowDisabled}
            onChange={(event) => {
              const previous = priority;
              const next = event.target.value as TaskPriority;
              setPriority(next);
              void updateField(
                { priority: next },
                `Task priority updated to ${next}.`,
                () => setPriority(previous),
              );
            }}
            className={selectClassName}
          >
            {priorities.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <form
          className="space-y-1.5 text-xs font-medium text-slate-400"
          onSubmit={(event) => {
            event.preventDefault();
            void updateField(
              { dueAt: dueAt ? new Date(dueAt).toISOString() : null },
              dueAt ? "Task due date updated." : "Task due date cleared.",
            );
          }}
        >
          <span className="block">Due date and time</span>
          <div className="flex gap-2">
            <input
              type="datetime-local"
              value={dueAt}
              disabled={rowDisabled}
              onChange={(event) => setDueAt(event.target.value)}
              aria-label={`Due date for ${task.title}`}
              className={inputClassName}
            />
            <button
              type="submit"
              disabled={rowDisabled || dueAt === toDateTimeLocalValue(task.dueAt)}
              aria-label={`Save due date for ${task.title}`}
              className={secondaryButtonClassName}
            >
              {rowPending ? <ButtonSpinner /> : <Save aria-hidden="true" className="h-4 w-4" />}
              <span className="sr-only sm:not-sr-only">Save</span>
            </button>
          </div>
        </form>
      </div>
    </article>
  );
}

export function TasksManager({
  tasks,
  total,
}: {
  tasks: TaskDto[];
  total: number;
}) {
  const router = useRouter();
  const createFormRef = useRef<HTMLFormElement>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPendingAction("create");
    setError(null);
    setSuccess(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const title = String(formData.get("title") ?? "").trim();
    const description = String(formData.get("description") ?? "").trim();
    const dueValue = String(formData.get("dueAt") ?? "").trim();
    const status = String(formData.get("status") ?? "todo") as TaskStatus;
    const priority = String(formData.get("priority") ?? "medium") as TaskPriority;

    if (!title) {
      setError("Task title is required.");
      setPendingAction(null);
      return;
    }

    try {
      await apiRequest<TaskDto>("/api/tasks", {
        method: "POST",
        body: {
          title,
          description: description || null,
          status,
          priority,
          dueAt: dueValue ? new Date(dueValue).toISOString() : null,
        },
      });
      createFormRef.current?.reset();
      setSuccess("Task created.");
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Task could not be created."));
    } finally {
      setPendingAction(null);
    }
  }

  async function updateTask(
    id: string,
    patch: {
      status?: TaskStatus;
      priority?: TaskPriority;
      dueAt?: string | null;
    },
    successMessage: string,
  ): Promise<boolean> {
    setPendingAction(`update:${id}`);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<TaskDto>(`/api/tasks/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: patch,
      });
      setSuccess(successMessage);
      router.refresh();
      return true;
    } catch (caught) {
      setError(getErrorMessage(caught, "Task could not be updated."));
      return false;
    } finally {
      setPendingAction(null);
    }
  }

  async function deleteTask(task: TaskDto) {
    setPendingAction(`delete:${task.id}`);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<void>(`/api/tasks/${encodeURIComponent(task.id)}`, {
        method: "DELETE",
      });
      setSuccess(`“${task.title}” deleted.`);
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Task could not be deleted."));
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="space-y-5">
      <Panel>
        <SectionHeading
          title="Create a task"
          description="Saved locally with the optional fields you provide"
        />
        <form
          ref={createFormRef}
          onSubmit={createTask}
          className="grid gap-4 p-5 md:grid-cols-2 2xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1.5fr)_9rem_9rem_minmax(13rem,1fr)_auto] 2xl:items-end"
        >
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Title</span>
            <input
              name="title"
              type="text"
              maxLength={200}
              required
              disabled={pendingAction === "create"}
              placeholder="What needs to be done?"
              className={inputClassName}
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Description <span className="text-slate-600">optional</span></span>
            <input
              name="description"
              type="text"
              maxLength={10_000}
              disabled={pendingAction === "create"}
              placeholder="Add useful context"
              className={inputClassName}
            />
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Status</span>
            <select name="status" defaultValue="todo" className={selectClassName}>
              {statuses.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Priority</span>
            <select name="priority" defaultValue="medium" className={selectClassName}>
              {priorities.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 text-xs font-medium text-slate-400">
            <span>Due <span className="text-slate-600">optional</span></span>
            <input name="dueAt" type="datetime-local" className={inputClassName} />
          </label>
          <button
            type="submit"
            disabled={pendingAction === "create"}
            className={primaryButtonClassName}
          >
            {pendingAction === "create" ? <ButtonSpinner /> : <Plus aria-hidden="true" className="h-4 w-4" />}
            Add task
          </button>
        </form>
      </Panel>

      {error ? <ErrorBanner title="Task request failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <Panel>
        <SectionHeading
          title="Task list"
          description={
            total > tasks.length
              ? `Showing ${tasks.length} of ${total} matching tasks`
              : `${total} matching ${total === 1 ? "task" : "tasks"}`
          }
          action={
            pendingAction ? (
              <span className="inline-flex items-center gap-2 text-xs text-cyan-200">
                <ButtonSpinner /> Saving change
              </span>
            ) : null
          }
        />
        {tasks.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {tasks.map((task) => (
              <TaskRow
                key={`${task.id}:${task.status}:${task.priority}:${task.dueAt ?? ""}`}
                task={task}
                disabled={pendingAction !== null}
                onUpdate={updateTask}
                onDelete={deleteTask}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={ListTodo}
            title="No tasks match this view"
            description="Create a task above or clear the filters to see the complete local task list."
          />
        )}
      </Panel>
    </div>
  );
}
