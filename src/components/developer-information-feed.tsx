import { AlertTriangle, Bug, Code2, FileCode2, RadioTower } from "lucide-react";
import { JsonViewer } from "@/components/json-viewer";
import {
  Badge,
  EmptyState,
  Panel,
  SectionHeading,
  StatusBadge,
} from "@/components/ui";
import type { DeveloperInformationDto } from "@/modules/developer-mode/contracts";

function severityTone(severity: string): "info" | "warning" | "danger" {
  if (severity === "critical" || severity === "error") return "danger";
  if (severity === "warning") return "warning";
  return "info";
}

export function DeveloperInformationFeed({
  items,
}: {
  items: DeveloperInformationDto[];
}) {
  return (
    <Panel>
      <SectionHeading
        title="Developer information"
        description="Read-only Core Brain updates shared with desktop and mobile"
        action={
          <span className="inline-flex items-center gap-2 text-xs text-slate-500">
            <RadioTower aria-hidden="true" className="h-3.5 w-3.5 text-cyan-300" />
            {items.length} update{items.length === 1 ? "" : "s"}
          </span>
        }
      />
      {items.length > 0 ? (
        <div className="divide-y divide-slate-800/80">
          {items.map((item) => {
            const proposal = item.proposal;
            return (
              <article key={item.eventId} className="space-y-4 p-5 sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-300/20 bg-amber-300/10 text-amber-200">
                      <Bug aria-hidden="true" className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        {item.type}
                      </p>
                      <h3 className="mt-1 break-words text-base font-semibold text-white">
                        {proposal?.title ?? "Developer event"}
                      </h3>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {proposal ? (
                      <Badge tone={severityTone(proposal.severity)} dot>
                        {proposal.severity}
                      </Badge>
                    ) : null}
                    <StatusBadge status={proposal?.status ?? "received"} />
                  </div>
                </div>

                {proposal ? (
                  <>
                    <div className="grid gap-3 rounded-xl border border-slate-800 bg-slate-950/45 p-4 text-sm sm:grid-cols-2">
                      <div className="flex items-center gap-2 text-slate-400">
                        <Code2 aria-hidden="true" className="h-4 w-4 text-slate-600" />
                        <span className="min-w-0 break-words">{proposal.repository}</span>
                      </div>
                      <div className="flex items-center gap-2 text-slate-400">
                        <FileCode2 aria-hidden="true" className="h-4 w-4 text-slate-600" />
                        <span className="min-w-0 break-words font-mono text-xs">
                          {proposal.file}
                          {proposal.line === null
                            ? ""
                            : `:${proposal.line}${
                                proposal.column === null ? "" : `:${proposal.column}`
                              }`}
                        </span>
                      </div>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                      {proposal.message}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
                      Explanation and title are displayed exactly as supplied by Core Brain.
                    </div>
                  </>
                ) : (
                  <JsonViewer value={item.payload} />
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Bug}
          title="No developer information yet"
          description="Core Brain developer events will appear here without exposing local analysis to the client."
        />
      )}
    </Panel>
  );
}
