"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  Braces,
  Play,
  Plus,
  Power,
  Trash2,
  Workflow,
  X,
} from "lucide-react";
import type { AutomationDto } from "@/modules/automations/contracts";
import { JsonViewer } from "@/components/json-viewer";
import { Switch } from "@/components/switch";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import { formatDateTime } from "@/lib/client/format";
import {
  Badge,
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  InlineNotice,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
  dangerButtonClassName,
  inputClassName,
  primaryButtonClassName,
  secondaryButtonClassName,
} from "@/components/ui";

interface AutomationRunResponse {
  actionId: string;
  success: boolean;
  status: "completed" | "pending_approval" | "rejected" | "failed";
  error?: string;
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} must contain valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

function parseConditions(value: string): Array<Record<string, unknown>> {
  if (!value.trim()) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error("Conditions must contain valid JSON when provided.");
  }
  if (!Array.isArray(parsed)) {
    throw new Error("Conditions must be a JSON array.");
  }
  if (parsed.some((item) => !item || typeof item !== "object" || Array.isArray(item))) {
    throw new Error("Each condition must be a JSON object.");
  }
  return parsed as Array<Record<string, unknown>>;
}

function AutomationCard({
  automation,
  disabled,
  onToggle,
  onRun,
  onDelete,
}: {
  automation: AutomationDto;
  disabled: boolean;
  onToggle: (automation: AutomationDto, enabled: boolean) => Promise<void>;
  onRun: (automation: AutomationDto) => Promise<void>;
  onDelete: (automation: AutomationDto) => Promise<void>;
}) {
  const [pending, setPending] = useState<"toggle" | "run" | "delete" | null>(null);
  const cardDisabled = disabled || pending !== null;

  return (
    <article className="px-5 py-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={automation.enabled ? "enabled" : "disabled"} />
            <Badge tone="info">{automation.triggerKind}</Badge>
            {automation.lastError ? <Badge tone="danger">Last run failed</Badge> : null}
          </div>
          <h3 className="mt-3 break-words text-base font-semibold text-slate-100">
            {automation.name}
          </h3>
          {automation.description ? (
            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-500">
              {automation.description}
            </p>
          ) : null}
          <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 xl:grid-cols-4">
            <div>
              <dt className="font-medium text-slate-600">Trigger</dt>
              <dd className="mt-1 break-all font-mono text-slate-300">
                {automation.triggerValue ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-slate-600">Action</dt>
              <dd className="mt-1 break-all font-mono text-cyan-200">{automation.action}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-600">Last run</dt>
              <dd className="mt-1 text-slate-400">{formatDateTime(automation.lastRunAt)}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-600">Next run</dt>
              <dd className="mt-1 text-slate-400">{formatDateTime(automation.nextRunAt)}</dd>
            </div>
          </dl>
          {automation.lastError ? (
            <p className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/[0.06] px-3 py-2 text-xs leading-5 text-rose-200">
              {automation.lastError}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3">
            <Switch
              checked={automation.enabled}
              disabled={cardDisabled}
              label={`${automation.enabled ? "Disable" : "Enable"} ${automation.name}`}
              onCheckedChange={(enabled) => {
                setPending("toggle");
                void onToggle(automation, enabled).finally(() => setPending(null));
              }}
            />
            <span className="text-xs text-slate-400">
              {automation.enabled ? "Enabled" : "Disabled"}
            </span>
          </div>
          <button
            type="button"
            disabled={cardDisabled}
            onClick={() => {
              setPending("run");
              void onRun(automation).finally(() => setPending(null));
            }}
            className={secondaryButtonClassName}
          >
            {pending === "run" ? <ButtonSpinner /> : <Play aria-hidden="true" className="h-4 w-4" />}
            Run now
          </button>
          <button
            type="button"
            disabled={cardDisabled}
            onClick={() => {
              if (!window.confirm(`Delete automation “${automation.name}”?`)) return;
              setPending("delete");
              void onDelete(automation).finally(() => setPending(null));
            }}
            className={dangerButtonClassName}
            aria-label={`Delete automation ${automation.name}`}
          >
            {pending === "delete" ? <ButtonSpinner /> : <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />}
            Delete
          </button>
        </div>
      </div>

      <details className="group mt-5 border-t border-slate-800/70 pt-4">
        <summary className="inline-flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50">
          <Braces aria-hidden="true" className="h-3.5 w-3.5 text-cyan-300" />
          Inspect configuration
        </summary>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <JsonViewer value={automation.actionPayload} label="Action payload" />
          <JsonViewer value={automation.conditions} label="Conditions" />
        </div>
      </details>
    </article>
  );
}

export function AutomationsManager({ automations }: { automations: AutomationDto[] }) {
  const router = useRouter();
  const [formOpen, setFormOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function createAutomation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPendingAction("create");
    setError(null);
    setSuccess(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const name = String(formData.get("name") ?? "").trim();
    const description = String(formData.get("description") ?? "").trim();
    const triggerValue = String(formData.get("triggerValue") ?? "").trim();
    const action = String(formData.get("action") ?? "").trim();
    const actionPayloadText = String(formData.get("actionPayload") ?? "{}");
    const conditionsText = String(formData.get("conditions") ?? "");
    const enabled = formData.get("enabled") === "on";

    try {
      if (!name || !triggerValue || !action) {
        throw new Error("Name, event type, and action are required.");
      }
      const actionPayload = parseJsonObject(actionPayloadText, "Action payload");
      const conditions = parseConditions(conditionsText);

      await apiRequest<AutomationDto>("/api/automations", {
        method: "POST",
        body: {
          name,
          description: description || null,
          enabled,
          triggerKind: "event",
          triggerValue,
          conditions,
          action,
          actionPayload,
        },
      });

      form.reset();
      setFormOpen(false);
      setSuccess("Event automation created.");
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Automation could not be created."));
    } finally {
      setPendingAction(null);
    }
  }

  async function toggleAutomation(automation: AutomationDto, enabled: boolean) {
    setPendingAction(`toggle:${automation.id}`);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<AutomationDto>(`/api/automations/${encodeURIComponent(automation.id)}`, {
        method: "PATCH",
        body: { enabled },
      });
      setSuccess(`“${automation.name}” ${enabled ? "enabled" : "disabled"}.`);
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Automation could not be updated."));
    } finally {
      setPendingAction(null);
    }
  }

  async function runAutomation(automation: AutomationDto) {
    setPendingAction(`run:${automation.id}`);
    setError(null);
    setSuccess(null);
    try {
      const response = await apiRequest<AutomationRunResponse>(
        `/api/automations/${encodeURIComponent(automation.id)}/run`,
        { method: "POST" },
      );
      if (response.status === "failed" || response.status === "rejected") {
        throw new Error(response.error || `Automation run ${response.status}.`);
      }
      setSuccess(
        response.status === "pending_approval"
          ? "Automation requested an action and is waiting for approval."
          : "Automation run completed.",
      );
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Automation could not be run."));
    } finally {
      setPendingAction(null);
    }
  }

  async function deleteAutomation(automation: AutomationDto) {
    setPendingAction(`delete:${automation.id}`);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<void>(`/api/automations/${encodeURIComponent(automation.id)}`, {
        method: "DELETE",
      });
      setSuccess(`“${automation.name}” deleted.`);
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Automation could not be deleted."));
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="space-y-5">
      <Panel>
        <SectionHeading
          title="Create an event automation"
          description="Use an exact normalized event type; templates such as {{ event.payload.id }} are resolved at run time"
          action={
            <button
              type="button"
              onClick={() => setFormOpen((open) => !open)}
              aria-expanded={formOpen}
              className={formOpen ? secondaryButtonClassName : primaryButtonClassName}
            >
              {formOpen ? <X aria-hidden="true" className="h-4 w-4" /> : <Plus aria-hidden="true" className="h-4 w-4" />}
              {formOpen ? "Close" : "New automation"}
            </button>
          }
        />
        {formOpen ? (
          <form onSubmit={createAutomation} className="space-y-5 p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Name</span>
                <input name="name" type="text" required maxLength={200} placeholder="Automation name" className={inputClassName} />
              </label>
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Description <span className="text-slate-600">optional</span></span>
                <input name="description" type="text" maxLength={2_000} placeholder="What this automation does" className={inputClassName} />
              </label>
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Trigger event type</span>
                <input
                  name="triggerValue"
                  type="text"
                  required
                  maxLength={256}
                  list="event-types"
                  placeholder="event.type"
                  className={inputClassName}
                />
                <datalist id="event-types">
                  <option value="connector.event" />
                </datalist>
              </label>
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Action</span>
                <input
                  name="action"
                  type="text"
                  required
                  maxLength={128}
                  list="automation-actions"
                  placeholder="tasks.create_task"
                  className={inputClassName}
                />
                <datalist id="automation-actions">
                  <option value="tasks.create_task" />
                  <option value="tasks.update_task" />
                  <option value="tasks.complete_task" />
                  <option value="calendar.create_event" />
                  <option value="calendar.update_event" />
                  <option value="jobs.save_job" />
                  <option value="jobs.ignore_job" />
                </datalist>
              </label>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Action payload JSON</span>
                <textarea
                  name="actionPayload"
                  rows={7}
                  required
                  spellCheck={false}
                  defaultValue="{}\n"
                  className={`${inputClassName} resize-y font-mono leading-6`}
                />
              </label>
              <label className="space-y-1.5 text-xs font-medium text-slate-400">
                <span>Conditions JSON <span className="text-slate-600">optional</span></span>
                <textarea
                  name="conditions"
                  rows={7}
                  spellCheck={false}
                  placeholder="[]"
                  className={`${inputClassName} resize-y font-mono leading-6`}
                />
              </label>
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <label className="inline-flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/50 px-4 text-sm text-slate-300">
                <input type="checkbox" name="enabled" defaultChecked className="h-4 w-4 rounded border-slate-600 bg-slate-900" />
                <Power aria-hidden="true" className="h-4 w-4 text-cyan-300" />
                Enable after creation
              </label>
              <button type="submit" disabled={pendingAction === "create"} className={primaryButtonClassName}>
                {pendingAction === "create" ? <ButtonSpinner /> : <Plus aria-hidden="true" className="h-4 w-4" />}
                Create automation
              </button>
            </div>
          </form>
        ) : null}
      </Panel>

      <InlineNotice>
        Manual runs use an explicit manual context. Event templates only resolve
        when the automation is triggered by a normalized event.
      </InlineNotice>
      {error ? <ErrorBanner title="Automation request failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <Panel>
        <SectionHeading
          title="Automations"
          description={`${automations.length} local ${automations.length === 1 ? "automation" : "automations"}`}
          action={
            pendingAction ? (
              <span className="inline-flex items-center gap-2 text-xs text-cyan-200">
                <ButtonSpinner /> Processing
              </span>
            ) : (
              <Activity aria-hidden="true" className="h-4 w-4 text-slate-500" />
            )
          }
        />
        {automations.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {automations.map((automation) => (
              <AutomationCard
                key={`${automation.id}:${automation.enabled}:${automation.updatedAt}`}
                automation={automation}
                disabled={pendingAction !== null}
                onToggle={toggleAutomation}
                onRun={runAutomation}
                onDelete={deleteAutomation}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Workflow}
            title="No automations configured"
            description="Create an event automation above. Nothing runs until it exists and is enabled."
          />
        )}
      </Panel>
    </div>
  );
}
