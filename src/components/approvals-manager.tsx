"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  CheckCheck,
  Clock3,
  Fingerprint,
  ShieldQuestion,
  X,
} from "lucide-react";
import type { ActionExecutionDto } from "@/modules/actions/contracts";
import { JsonViewer } from "@/components/json-viewer";
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
  SuccessBanner,
  inputClassName,
  primaryButtonClassName,
  secondaryButtonClassName,
} from "@/components/ui";

interface DecisionResponse {
  actionId: string;
  success: boolean;
  status: "completed" | "pending_approval" | "rejected" | "failed";
  error?: string;
}

function ApprovalCard({
  action,
  disabled,
  onDecision,
}: {
  action: ActionExecutionDto;
  disabled: boolean;
  onDecision: (
    id: string,
    decision: "approve" | "reject",
    reason?: string,
  ) => Promise<boolean>;
}) {
  const [reason, setReason] = useState("");
  const [pendingDecision, setPendingDecision] = useState<"approve" | "reject" | null>(null);
  const rowDisabled = disabled || pendingDecision !== null;

  async function decide(decision: "approve" | "reject") {
    setPendingDecision(decision);
    const succeeded = await onDecision(action.id, decision, reason.trim() || undefined);
    if (succeeded) setReason("");
    setPendingDecision(null);
  }

  return (
    <article className="px-5 py-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="warning" dot>Pending approval</Badge>
            <Badge>{action.permissionLevel ?? "Policy resolved"}</Badge>
          </div>
          <h3 className="mt-3 break-all font-mono text-base font-semibold text-cyan-100">
            {action.action}
          </h3>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500">
            <span>Source: {action.source}</span>
            <span className="inline-flex items-center gap-1.5">
              <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />
              Requested {formatDateTime(action.requestedAt)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Fingerprint aria-hidden="true" className="h-3.5 w-3.5" />
              {action.attempts} prior {action.attempts === 1 ? "attempt" : "attempts"}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-5">
        <JsonViewer value={action.payload} label="Structured action payload" />
      </div>

      <div className="mt-5 grid gap-3 border-t border-slate-800/70 pt-5 lg:grid-cols-[minmax(14rem,1fr)_auto] lg:items-end">
        <label className="space-y-1.5 text-xs font-medium text-slate-400">
          <span>Decision reason <span className="text-slate-600">optional</span></span>
          <input
            type="text"
            value={reason}
            maxLength={1_000}
            disabled={rowDisabled}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Add context for the audit record"
            className={inputClassName}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={rowDisabled}
            onClick={() => void decide("approve")}
            className={primaryButtonClassName}
          >
            {pendingDecision === "approve" ? (
              <ButtonSpinner />
            ) : (
              <Check aria-hidden="true" className="h-4 w-4" />
            )}
            Approve
          </button>
          <button
            type="button"
            disabled={rowDisabled}
            onClick={() => void decide("reject")}
            className={secondaryButtonClassName}
          >
            {pendingDecision === "reject" ? (
              <ButtonSpinner />
            ) : (
              <X aria-hidden="true" className="h-4 w-4" />
            )}
            Reject
          </button>
        </div>
      </div>
    </article>
  );
}

export function ApprovalsManager({ actions }: { actions: ActionExecutionDto[] }) {
  const router = useRouter();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function decide(
    id: string,
    decision: "approve" | "reject",
    reason?: string,
  ): Promise<boolean> {
    setPendingId(id);
    setError(null);
    setSuccess(null);
    try {
      const response = await apiRequest<DecisionResponse>(
        `/api/actions/${encodeURIComponent(id)}/${decision}`,
        {
          method: "POST",
          body: reason ? { reason } : {},
        },
      );

      if (decision === "approve" && response.status !== "completed") {
        throw new Error(response.error || "The action did not complete after approval.");
      }
      if (decision === "reject" && response.status !== "rejected") {
        throw new Error(response.error || "The action was not rejected.");
      }

      setResolvedIds((current) => new Set(current).add(id));
      setSuccess(
        decision === "approve"
          ? "Action approved and executed."
          : "Action rejected.",
      );
      router.refresh();
      return true;
    } catch (caught) {
      setError(getErrorMessage(caught, "The approval decision could not be saved."));
      return false;
    } finally {
      setPendingId(null);
    }
  }

  const visibleActions = actions.filter((action) => !resolvedIds.has(action.id));

  return (
    <div className="space-y-5">
      <InlineNotice>
        Approval executes the registered action immediately. Review the structured
        payload and permission level before deciding.
      </InlineNotice>
      {error ? <ErrorBanner title="Decision failed" message={error} /> : null}
      {success ? <SuccessBanner message={success} /> : null}

      <Panel>
        <SectionHeading
          title="Decision queue"
          description="Only actions in pending_approval state are shown"
          action={
            pendingId ? (
              <span className="inline-flex items-center gap-2 text-xs text-cyan-200">
                <ButtonSpinner /> Processing action
              </span>
            ) : null
          }
        />
        {visibleActions.length > 0 ? (
          <div className="divide-y divide-slate-800/80">
            {visibleActions.map((action) => (
              <ApprovalCard
                key={action.id}
                action={action}
                disabled={pendingId !== null}
                onDecision={decide}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={actions.length > 0 ? CheckCheck : ShieldQuestion}
            title={actions.length > 0 ? "Decision recorded" : "Approval queue is clear"}
            description={
              actions.length > 0
                ? "The selected action has left the pending queue."
                : "No action is currently waiting for a human decision."
            }
          />
        )}
      </Panel>
    </div>
  );
}
