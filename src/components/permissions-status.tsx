import {
  BrainCircuit,
  Database,
  KeyRound,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import type { AccessGroup, AccessState, AccessStatus } from "@/lib/access-status";
import { Badge, Panel, SectionHeading, cn } from "@/components/ui";

/**
 * The access status matrix.
 *
 * Every row states one observed fact and carries its state as text, not only as
 * a colour, because the colours are the same three tones the rest of the app
 * uses for status and a reader should not have to learn a second vocabulary.
 * `value` sits on the right as a monospace figure so the column of numbers lines
 * up and can be scanned, which is the part people actually come here for.
 */

const GROUP_ICONS: Record<string, LucideIcon> = {
  storage: Database,
  gemini: KeyRound,
  brain: BrainCircuit,
  workspace: ShieldCheck,
};

const STATE_TONE = {
  ok: "success",
  warn: "warning",
  error: "danger",
  unknown: "neutral",
} as const;

const STATE_LABEL: Record<AccessState, string> = {
  ok: "OK",
  warn: "Review",
  error: "Error",
  unknown: "Info",
};

function GroupPanel({ group }: { group: GroupPanelProps }) {
  const Icon = GROUP_ICONS[group.id] ?? ShieldCheck;
  const failing = group.checks.filter((c) => c.state === "error").length;
  const reviewing = group.checks.filter((c) => c.state === "warn").length;

  return (
    <Panel className="flex flex-col">
      <SectionHeading
        title={group.title}
        description={group.description}
        action={
          failing > 0 ? (
            <Badge tone="danger" dot>
              {failing} failing
            </Badge>
          ) : reviewing > 0 ? (
            <Badge tone="warning" dot>
              {reviewing} to review
            </Badge>
          ) : (
            <Badge tone="success" dot>
              All clear
            </Badge>
          )
        }
      />
      <ul className="divide-y divide-zinc-800/80 border-t border-zinc-800/80">
        {group.checks.map((check) => (
          <li
            key={check.id}
            className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start sm:gap-4"
          >
            <span
              aria-hidden="true"
              className={cn(
                "mt-0.5 hidden h-7 w-7 shrink-0 items-center justify-center rounded-lg border sm:flex",
                check.state === "error"
                  ? "border-rose-400/30 bg-rose-400/10 text-rose-300"
                  : check.state === "warn"
                    ? "border-amber-400/30 bg-amber-400/10 text-amber-300"
                    : "border-zinc-700 bg-zinc-800/70 text-zinc-400",
              )}
            >
              <Icon className="h-3.5 w-3.5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-medium text-zinc-200">{check.label}</h3>
                <Badge tone={STATE_TONE[check.state]}>{STATE_LABEL[check.state]}</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-5 text-zinc-450">{check.detail}</p>
            </div>
            <p className="shrink-0 font-mono text-xs text-zinc-400 sm:pt-0.5 sm:text-right">
              {check.value}
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

type GroupPanelProps = AccessGroup;

export function PermissionsStatus({ status }: { status: AccessStatus }) {
  const attention = status.total - status.ok;

  return (
    <section aria-label="Access status" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-zinc-200">
            Access status
          </h2>
          <p className="mt-1 text-xs leading-5 text-zinc-450">
            Observed live from this workspace. No credential is ever read or shown
            here — only whether one is configured and who holds it.
          </p>
        </div>
        <p className="text-xs text-zinc-450">
          <span className="font-semibold text-zinc-200">{status.ok}</span> of{" "}
          {status.total} checks passing
          {attention > 0 ? (
            <span className="text-zinc-450"> · {attention} need attention</span>
          ) : null}
        </p>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        {status.groups.map((group) => (
          <GroupPanel key={group.id} group={group} />
        ))}
      </div>
    </section>
  );
}
