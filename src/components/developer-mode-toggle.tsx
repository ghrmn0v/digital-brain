"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Code2, MonitorSmartphone, ShieldCheck } from "lucide-react";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  ButtonSpinner,
  ErrorBanner,
  Panel,
  SectionHeading,
  SuccessBanner,
} from "@/components/ui";
import { Switch } from "@/components/switch";

export function DeveloperModeToggle({ enabled }: { enabled: boolean }) {
  const router = useRouter();
  const [active, setActive] = useState(enabled);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function update(nextEnabled: boolean) {
    const previous = active;
    setActive(nextEnabled);
    setPending(true);
    setError(null);
    setSuccess(null);
    try {
      await apiRequest<{ enabled: boolean }>("/api/developer-mode", {
        method: "PUT",
        headers: { "x-product-client-platform": "desktop" },
        body: { enabled: nextEnabled },
      });
      setSuccess(
        nextEnabled
          ? "Developer Mode enabled for the desktop workspace."
          : "Developer Mode disabled. Shared developer information remains available.",
      );
      router.refresh();
    } catch (caught) {
      setActive(previous);
      setError(
        getErrorMessage(caught, "Developer Mode could not be updated."),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <Panel>
        <SectionHeading
          title="Developer Mode"
          description="Desktop capability for repository context, developer proposals, permissions, and Fly workflow"
          action={
            <Switch
              checked={active}
              disabled={pending}
              onCheckedChange={(value) => void update(value)}
              label="Toggle desktop Developer Mode"
            />
          }
        />
        <div className="grid gap-4 p-5 md:grid-cols-3">
          <div className="flex gap-3">
            <Code2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
            <div>
              <p className="text-sm font-semibold text-slate-200">Desktop only</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                The full workspace and developer actions never appear on mobile.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <MonitorSmartphone aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
            <div>
              <p className="text-sm font-semibold text-slate-200">Shared information</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Mobile keeps read-only access to Core Brain developer updates.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <ShieldCheck aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <div>
              <p className="text-sm font-semibold text-slate-200">No auto-fix</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Approval records a proposal only; no Git, test, or deployment action runs.
              </p>
            </div>
          </div>
        </div>
        {pending ? (
          <div className="flex items-center gap-2 border-t border-slate-800 px-5 py-3 text-xs text-cyan-200">
            <ButtonSpinner /> Saving desktop capability
          </div>
        ) : null}
      </Panel>
      {error ? <ErrorBanner title="Developer Mode update failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}
    </div>
  );
}
