import Link from "next/link";
import {
  ArrowRight,
  BrainCircuit,
  CheckCheck,
  ShieldCheck,
  Workflow,
} from "@/components/icons";
import { Badge, Panel } from "@/components/ui";

export function AiOperationsPanel({
  coreBrainConfigured,
  pendingApprovals,
  enabledAutomations,
  permissionSummary,
}: {
  coreBrainConfigured: boolean;
  pendingApprovals: number;
  enabledAutomations: number;
  permissionSummary: { automatic: number; askFirst: number; off: number };
}) {
  return (
    <Panel className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-[var(--accent)]/[0.07] blur-3xl"
      />
      <div className="relative grid gap-7 p-6 lg:grid-cols-[1.15fr_1fr] lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/10 text-[var(--accent)]">
              <BrainCircuit aria-hidden="true" className="h-5 w-5" />
            </div>
            <Badge tone={coreBrainConfigured ? "success" : "warning"} dot>
              {coreBrainConfigured ? "Core Brain connected" : "Core Brain channel pending"}
            </Badge>
          </div>
          <h2 className="mt-5 text-xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-2xl">
            AI operates the product. You keep control.
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
            Core Brain and automations use the action API directly. Product checks
            permission, executes supported actions, records the result, and only
            interrupts you when policy is <strong className="text-[var(--warning)]">ASK_FIRST</strong>.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/settings#approvals"
              className="control-button inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--accent-ink)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/60"
            >
              Review AI decisions
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link
              href="/settings#permissions"
              className="control-button inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
            >
              Control permissions
            </Link>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)]/70 p-4">
            <Workflow aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />
            <p className="mt-3 text-2xl font-semibold text-[var(--text-primary)]">{enabledAutomations}</p>
            <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">Active automations</p>
          </div>
          <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)]/70 p-4">
            <CheckCheck aria-hidden="true" className="h-4 w-4 text-[var(--warning)]" />
            <p className="mt-3 text-2xl font-semibold text-[var(--text-primary)]">{pendingApprovals}</p>
            <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">Waiting for you</p>
          </div>
          <div className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)]/70 p-4">
            <ShieldCheck aria-hidden="true" className="h-4 w-4 text-[var(--success)]" />
            <p className="mt-3 text-2xl font-semibold text-[var(--text-primary)]">
              {permissionSummary.automatic}
            </p>
            <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
              Automatic Â· {permissionSummary.askFirst} ask Â· {permissionSummary.off} off
            </p>
          </div>
        </div>
      </div>
    </Panel>
  );
}
