import Link from "next/link";
import {
  ArrowRight,
  BrainCircuit,
  CheckCheck,
  ShieldCheck,
  Workflow,
} from "lucide-react";
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
        className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-cyan-400/[0.07] blur-3xl"
      />
      <div className="relative grid gap-7 p-6 lg:grid-cols-[1.15fr_1fr] lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
              <BrainCircuit aria-hidden="true" className="h-5 w-5" />
            </div>
            <Badge tone={coreBrainConfigured ? "success" : "warning"} dot>
              {coreBrainConfigured ? "Core Brain connected" : "Core Brain channel pending"}
            </Badge>
          </div>
          <h2 className="mt-5 text-xl font-semibold tracking-tight text-white sm:text-2xl">
            AI operates the product. You keep control.
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
            Core Brain and automations use the action API directly. Product checks
            permission, executes supported actions, records the result, and only
            interrupts you when policy is <strong className="text-amber-200">ASK_FIRST</strong>.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              href="/approvals"
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60"
            >
              Review AI decisions
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link
              href="/permissions"
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50"
            >
              Control permissions
            </Link>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-4">
            <Workflow aria-hidden="true" className="h-4 w-4 text-cyan-300" />
            <p className="mt-3 text-2xl font-semibold text-white">{enabledAutomations}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Active automations</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-4">
            <CheckCheck aria-hidden="true" className="h-4 w-4 text-amber-300" />
            <p className="mt-3 text-2xl font-semibold text-white">{pendingApprovals}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Waiting for you</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/55 p-4">
            <ShieldCheck aria-hidden="true" className="h-4 w-4 text-emerald-300" />
            <p className="mt-3 text-2xl font-semibold text-white">
              {permissionSummary.automatic}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Automatic · {permissionSummary.askFirst} ask · {permissionSummary.off} off
            </p>
          </div>
        </div>
      </div>
    </Panel>
  );
}
