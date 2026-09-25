"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, SlidersHorizontal } from "lucide-react";
import type { PermissionDto } from "@/modules/permissions/contracts";
import { Switch } from "@/components/switch";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  ButtonSpinner,
  EmptyState,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
  selectClassName,
} from "@/components/ui";

type PermissionLevel = "AUTOMATIC" | "ASK_FIRST" | "OFF";

const levels: Array<{ value: PermissionLevel; label: string }> = [
  { value: "AUTOMATIC", label: "Automatic" },
  { value: "ASK_FIRST", label: "Ask first" },
  { value: "OFF", label: "Off" },
];

function PermissionRow({
  permission,
  disabled,
  onSaved,
  onSavingChange,
}: {
  permission: PermissionDto;
  disabled: boolean;
  onSaved: (message: string) => void;
  onSavingChange: (saving: boolean) => void;
}) {
  const router = useRouter();
  const [level, setLevel] = useState<PermissionLevel>(permission.level);
  const [enabled, setEnabled] = useState(permission.enabled);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rowDisabled = disabled || pending;

  async function save(patch: { level?: PermissionLevel; enabled?: boolean }) {
    setPending(true);
    onSavingChange(true);
    setError(null);
    try {
      const updated = await apiRequest<PermissionDto>(
        `/api/permissions/${encodeURIComponent(permission.id)}`,
        { method: "PATCH", body: patch },
      );
      setLevel(updated.level);
      setEnabled(updated.enabled);
      onSaved(
        patch.enabled !== undefined
          ? `${permission.action} ${updated.enabled ? "enabled" : "disabled"}.`
          : `${permission.action} set to ${updated.level.toLowerCase().replace("_", " ")}.`,
      );
      router.refresh();
    } catch (caught) {
      setLevel(permission.level);
      setEnabled(permission.enabled);
      setError(getErrorMessage(caught, "Permission policy could not be updated."));
    } finally {
      setPending(false);
      onSavingChange(false);
    }
  }

  return (
    <>
      <tr className="border-t border-slate-800/80 hover:bg-slate-800/20">
        <th scope="row" className="px-5 py-4 text-left align-top">
          <code className="break-all font-mono text-xs font-semibold text-cyan-200">
            {permission.action}
          </code>
          {permission.description ? (
            <p className="mt-1.5 max-w-lg text-xs leading-5 text-slate-500">
              {permission.description}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="mt-2 max-w-md text-xs leading-5 text-rose-300">
              {error}
            </p>
          ) : null}
        </th>
        <td className="px-5 py-4 align-top">
          <StatusBadge status={level} />
        </td>
        <td className="px-5 py-4 align-top">
          <label className="block min-w-36 space-y-1.5 text-xs font-medium text-slate-400">
            <span className="sr-only">Permission level for {permission.action}</span>
            <select
              value={level}
              disabled={rowDisabled}
              onChange={(event) => {
                const next = event.target.value as PermissionLevel;
                setLevel(next);
                void save({ level: next });
              }}
              className={selectClassName}
            >
              {levels.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </td>
        <td className="px-5 py-4 align-top">
          <div className="flex items-center gap-3">
            <Switch
              checked={enabled}
              disabled={rowDisabled}
              label={`${enabled ? "Disable" : "Enable"} ${permission.action}`}
              onCheckedChange={(next) => {
                setEnabled(next);
                void save({ enabled: next });
              }}
            />
            <span className="text-xs text-slate-500">{enabled ? "Enabled" : "Disabled"}</span>
            {pending ? <ButtonSpinner /> : null}
          </div>
        </td>
      </tr>
    </>
  );
}

export function PermissionsManager({ permissions }: { permissions: PermissionDto[] }) {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const groups = permissions.reduce<Record<string, PermissionDto[]>>(
    (result, permission) => {
      (result[permission.source] ??= []).push(permission);
      return result;
    },
    {},
  );

  return (
    <div className="space-y-5">
      {success ? <SuccessBanner message={success} /> : null}

      {permissions.length > 0 ? (
        <div className="space-y-5">
          {Object.entries(groups)
            .sort(([left], [right]) => left.localeCompare(right))
            .map(([source, sourcePermissions]) => (
              <Panel key={source}>
                <SectionHeading
                  title={source}
                  description={`${sourcePermissions.length} ${sourcePermissions.length === 1 ? "policy" : "policies"} for this source`}
                  action={
                    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                      <SlidersHorizontal aria-hidden="true" className="h-3.5 w-3.5" />
                      Policy controls
                    </span>
                  }
                />
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] border-collapse text-left">
                    <caption className="sr-only">Permission policies for {source}</caption>
                    <thead>
                      <tr className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                        <th scope="col" className="px-5 py-3">Action</th>
                        <th scope="col" className="px-5 py-3">Current</th>
                        <th scope="col" className="px-5 py-3">Level</th>
                        <th scope="col" className="px-5 py-3">Enabled</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sourcePermissions.map((permission) => (
                        <PermissionRow
                          key={`${permission.id}:${permission.level}:${permission.enabled}:${permission.updatedAt}`}
                          permission={permission}
                          disabled={pendingId !== null}
                          onSaved={setSuccess}
                          onSavingChange={(saving) => {
                            setPendingId(saving ? permission.id : null);
                            if (saving) setSuccess(null);
                          }}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            ))}
        </div>
      ) : (
        <Panel>
          <EmptyState
            icon={ShieldCheck}
            title="No permission policies"
            description="No local policy records exist. Unconfigured actions fall back to ASK_FIRST by design."
          />
        </Panel>
      )}
    </div>
  );
}
