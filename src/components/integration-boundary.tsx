import Link from "next/link";
import {
  ArrowRight,
  Cable,
  CircleOff,
  DatabaseZap,
  LockKeyhole,
  Settings2,
  Shapes,
} from "lucide-react";
import {
  Badge,
  InlineNotice,
  PageHeader,
  Panel,
  cn,
} from "@/components/ui";

const requiredContract = [
  {
    title: "Server-side adapter only",
    description:
      "A typed Core Brain read adapter must run on the server; browser bundles must never receive integration tokens.",
  },
  {
    title: "Stable, normalized records",
    description:
      "The adapter must map Core Brain records to the agreed Product DTOs with stable IDs, timestamps, and explicit source metadata.",
  },
  {
    title: "Deterministic pagination",
    description:
      "A cursor or equivalent stable pagination contract is required before lists can be loaded without duplicating or dropping records.",
  },
  {
    title: "Explicit failure semantics",
    description:
      "Authentication, unavailable, empty, and partial-data states must remain distinguishable from a genuinely empty result.",
  },
] as const;

export function IntegrationBoundary({
  kind,
  configured,
}: {
  kind: "memory" | "people";
  configured: boolean;
}) {
  const singular = kind === "memory" ? "memory record" : "person record";
  const Icon = kind === "memory" ? DatabaseZap : Shapes;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Integration boundary"
        title={kind === "memory" ? "Memory" : "People"}
        description={
          kind === "memory"
            ? "A deliberate boundary for Core Brain memories. No memories are inferred or generated inside Product."
            : "A deliberate boundary for Core Brain people data. No people are inferred or generated inside Product."
        }
      />

      <Panel className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-cyan-400/[0.06] blur-3xl"
        />
        <div className="relative grid gap-8 p-6 sm:p-8 lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="max-w-3xl">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
              <Icon aria-hidden="true" className="h-6 w-6" />
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <h2 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">
                {configured
                  ? "Core Brain adapter not yet configured"
                  : "Core Brain not connected"}
              </h2>
              <Badge tone={configured ? "warning" : "neutral"} dot>
                {configured ? "URL configured" : "URL missing"}
              </Badge>
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">
              {configured
                ? "CORE_BRAIN_URL is present, but the agreed Core Brain read adapter is not configured. Product will not invent an API, request an undocumented endpoint, or display synthetic data."
                : "Set CORE_BRAIN_URL on the server to prepare the outbound integration. A read adapter and its contract are still required before this screen can display real records."}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/settings"
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              >
                <Settings2 aria-hidden="true" className="h-4 w-4" />
                Integration readiness
              </Link>
            </div>
          </div>
          <div className="flex h-32 w-32 items-center justify-center rounded-[2rem] border border-slate-800 bg-slate-950/70 text-slate-600 lg:h-40 lg:w-40">
            {configured ? (
              <Cable aria-hidden="true" className="h-12 w-12" />
            ) : (
              <CircleOff aria-hidden="true" className="h-12 w-12" />
            )}
          </div>
        </div>
      </Panel>

      <div className="grid gap-5 xl:grid-cols-[1fr_0.72fr]">
        <Panel>
          <div className="border-b border-slate-800 px-5 py-4 sm:px-6">
            <h2 className="text-sm font-semibold text-slate-100">
              Required read contract
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              These are implementation requirements, not assumed endpoints.
            </p>
          </div>
          <ol className="divide-y divide-slate-800/80">
            {requiredContract.map((item, index) => (
              <li key={item.title} className="flex gap-4 px-5 py-5 sm:px-6">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800 text-[11px] font-semibold text-cyan-200">
                  {index + 1}
                </span>
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">
                    {item.title}
                  </h3>
                  <p className="mt-1.5 text-sm leading-6 text-slate-500">
                    {item.description}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>

        <div className="space-y-5">
          <InlineNotice>
            The current normalized-event delivery contract is outbound-only. It
            does not define a Core Brain {singular} read API.
          </InlineNotice>
          <Panel className="p-5 sm:p-6">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
              <LockKeyhole aria-hidden="true" className="h-4 w-4 text-cyan-300" />
              Security boundary
            </div>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-500">
              <li>CORE_BRAIN_API_TOKEN remains server-only.</li>
              <li>URLs and credential values are never passed to Client Components.</li>
              <li>Only configured booleans are exposed on integration screens.</li>
            </ul>
            <Link
              href="/connectors"
              className={cn(
                "mt-5 inline-flex items-center gap-2 text-sm font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50",
              )}
            >
              Review connector state
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </Panel>
        </div>
      </div>
    </div>
  );
}
