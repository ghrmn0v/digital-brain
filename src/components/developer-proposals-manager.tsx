"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Code2, FileCode2, ShieldCheck, X } from "lucide-react";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  Badge,
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  Panel,
  SectionHeading,
  StatusBadge,
  SuccessBanner,
  dangerButtonClassName,
  primaryButtonClassName,
} from "@/components/ui";
import type { DeveloperProposalDto } from "@/modules/developer-mode/contracts";

export function DeveloperProposalsManager({
  initialProposals,
}: {
  initialProposals: DeveloperProposalDto[];
}) {
  const router = useRouter();
  const [proposals, setProposals] = useState(initialProposals);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function decide(proposal: DeveloperProposalDto, decision: "approve" | "reject") {
    setPendingId(proposal.id);
    setError(null);
    setSuccess(null);
    try {
      const updated = await apiRequest<DeveloperProposalDto>(
        `/api/developer-proposals/${encodeURIComponent(proposal.id)}/${decision}`,
        {
          method: "POST",
          headers: { "x-product-client-platform": "desktop" },
          body: {},
        },
      );
      setProposals((items) =>
        items.map((item) => (item.id === updated.id ? updated : item)),
      );
      setSuccess(
        decision === "approve"
          ? "Proposal approved. No external action was executed."
          : "Proposal rejected. No external action was executed.",
      );
      router.refresh();
    } catch (caught) {
      setError(getErrorMessage(caught, "Developer proposal could not be updated."));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <Panel>
        <SectionHeading
          title="Core Brain proposals"
          description="Approval changes proposal state only; Product does not run Git, tests, deployment, or fixes"
          action={
            <span className="inline-flex items-center gap-2 text-xs text-slate-500">
              <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5 text-cyan-300" />
              Permission required
            </span>
          }
        />
        {error ? (
          <div className="p-4 pb-0">
            <ErrorBanner title="Proposal decision failed" message={error} />
          </div>
        ) : null}
        {success ? (
          <div className="p-4 pb-0">
            <SuccessBanner message={success} />
          </div>
        ) : null}
        {proposals.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {proposals.map((proposal) => {
              const pending = pendingId === proposal.id;
              return (
                <article key={proposal.id} className="space-y-4 p-5 sm:p-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">
                        AI proposal
                      </p>
                      <h3 className="mt-1 text-base font-semibold text-white">
                        {proposal.title}
                      </h3>
                    </div>
                    <div className="flex gap-2">
                      <Badge tone={proposal.severity === "warning" ? "warning" : "info"} dot>
                        {proposal.severity}
                      </Badge>
                      <StatusBadge status={proposal.status.toLowerCase()} />
                    </div>
                  </div>
                  <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                    <span className="inline-flex items-center gap-2">
                      <Code2 aria-hidden="true" className="h-3.5 w-3.5" />
                      {proposal.repository}
                    </span>
                    <span className="inline-flex min-w-0 items-center gap-2 font-mono">
                      <FileCode2 aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">
                        {proposal.file}
                        {proposal.line === null ? "" : `:${proposal.line}`}
                      </span>
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                    {proposal.message}
                  </p>
                  {proposal.status === "PENDING" ? (
                    <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-4">
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => void decide(proposal, "approve")}
                        className={primaryButtonClassName}
                      >
                        {pending ? <ButtonSpinner /> : <Check aria-hidden="true" className="h-4 w-4" />}
                        Approve proposal
                      </button>
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => void decide(proposal, "reject")}
                        className={dangerButtonClassName}
                      >
                        <X aria-hidden="true" className="h-4 w-4" />
                        Reject
                      </button>
                    </div>
                  ) : (
                    <div className="border-t border-slate-800 pt-4 text-xs text-slate-500">
                      Decision recorded{proposal.decidedBy ? ` by ${proposal.decidedBy}` : ""}. No action execution is attached.
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={ShieldCheck}
            title="No developer proposals"
            description="Validated Core Brain bug events will appear here when Developer Mode is enabled."
          />
        )}
      </Panel>
    </div>
  );
}
