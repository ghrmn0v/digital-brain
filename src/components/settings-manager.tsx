"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Braces, Save, Settings2, Trash2 } from "lucide-react";
import type { SettingDto } from "@/modules/settings/contracts";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import { formatDateTime } from "@/lib/client/format";
import {
  ButtonSpinner,
  EmptyState,
  InlineNotice,
  Panel,
  SectionHeading,
  SuccessBanner,
  dangerButtonClassName,
  inputClassName,
  primaryButtonClassName,
} from "@/components/ui";

function SettingEditor({
  setting,
  disabled,
  onPending,
  onSaved,
}: {
  setting: SettingDto;
  disabled: boolean;
  onPending: (key: string | null) => void;
  onSaved: (message: string) => void;
}) {
  const router = useRouter();
  const [valueText, setValueText] = useState(
    () => JSON.stringify(setting.value, null, 2) ?? "null",
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    onPending(setting.key);
    setError(null);
    try {
      let value: unknown;
      try {
        value = JSON.parse(valueText);
      } catch {
        throw new Error("Setting value must be valid JSON.");
      }
      await apiRequest<SettingDto>("/api/settings", {
        method: "PUT",
        body: { key: setting.key, value },
      });
      onSaved(`Setting “${setting.key}” saved.`);
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Setting could not be saved."));
    } finally {
      setPending(false);
      onPending(null);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete setting “${setting.key}”?`)) return;
    setPending(true);
    onPending(setting.key);
    setError(null);
    try {
      await apiRequest<void>(
        `/api/settings/${encodeURIComponent(setting.key)}`,
        { method: "DELETE" },
      );
      onSaved(`Setting “${setting.key}” deleted.`);
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Setting could not be deleted."));
    } finally {
      setPending(false);
      onPending(null);
    }
  }

  return (
    <article className="px-5 py-5">
      <form onSubmit={save}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="break-all font-mono text-sm font-semibold text-cyan-200">
              {setting.key}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Updated {formatDateTime(setting.updatedAt)}
            </p>
          </div>
          <button
            type="button"
            disabled={disabled || pending}
            onClick={() => void remove()}
            className={dangerButtonClassName}
            aria-label={`Delete setting ${setting.key}`}
          >
            <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
            Delete
          </button>
        </div>
        <label className="mt-4 block space-y-1.5 text-xs font-medium text-slate-400">
          <span>JSON value</span>
          <textarea
            value={valueText}
            onChange={(event) => setValueText(event.target.value)}
            disabled={disabled || pending}
            rows={6}
            spellCheck={false}
            className={`${inputClassName} resize-y font-mono leading-6`}
          />
        </label>
        {error ? (
          <p role="alert" className="mt-2 text-xs leading-5 text-rose-300">{error}</p>
        ) : null}
        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={disabled || pending || valueText === (JSON.stringify(setting.value, null, 2) ?? "null")}
            className={primaryButtonClassName}
          >
            {pending ? <ButtonSpinner /> : <Save aria-hidden="true" className="h-4 w-4" />}
            Save setting
          </button>
        </div>
      </form>
    </article>
  );
}

export function SettingsManager({ settings }: { settings: SettingDto[] }) {
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  return (
    <div className="space-y-5">
      <InlineNotice>
        Store product preferences here, not credentials. Integration screens expose
        configured booleans only, and API tokens remain server environment values.
      </InlineNotice>
      {success ? <SuccessBanner message={success} /> : null}

      <Panel>
        <SectionHeading
          title="Product settings"
          description="Existing JSON-safe values from the local settings registry"
          action={
            <span className="inline-flex items-center gap-2 text-xs text-slate-500">
              <Braces aria-hidden="true" className="h-3.5 w-3.5" />
              {settings.length} {settings.length === 1 ? "setting" : "settings"}
            </span>
          }
        />
        {settings.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {settings.map((setting) => (
              <SettingEditor
                key={`${setting.key}:${setting.updatedAt}`}
                setting={setting}
                disabled={pendingKey !== null}
                onPending={setPendingKey}
                onSaved={setSuccess}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Settings2}
            title="No product settings"
            description="The local settings registry is empty. No unverified defaults are invented by this screen."
          />
        )}
      </Panel>
    </div>
  );
}
