"use client";

import { useState } from "react";
import { BrainCircuit } from "@/components/icons";
import { apiRequest, getErrorMessage } from "@/lib/client/api";

/**
 * The Fly 3D engine control.
 *
 * Fly is a separate local process that Product does not start, so from inside
 * the app the only honest thing to offer is a real status plus a real control.
 * Both are the server's: this component never guesses from configuration,
 * because "the URL is configured" and "the service is up" are different claims
 * and only the second is useful.
 *
 * Starting and stopping a process is a genuine capability, so it is kept behind
 * a single verb sent to the server, which owns the argv. Nothing typed here
 * reaches a shell.
 */

interface FlyStatus {
  reachable: boolean;
  origin: string;
  service: string | null;
  graph: string | null;
  neurons: number | null;
  flightMode: boolean | null;
  error: string | null;
  pid: number | null;
}

interface ControlResponse {
  ok: boolean;
  action: "start" | "stop";
  status: FlyStatus;
  reason?: string;
  note?: string;
}

export function FlyEngineControl({ initial }: { initial: FlyStatus }) {
  const [status, setStatus] = useState<FlyStatus>(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(action: "start" | "stop") {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      // apiRequest resolves to the response payload itself, not an envelope.
      const result = await apiRequest<ControlResponse>("/api/fly/control", {
        method: "POST",
        body: { action },
      });
      setStatus(result.status);
      if (result.ok) {
        setMessage(result.note ?? `Fly ${action} succeeded.`);
      } else {
        setError(result.reason ?? `Could not ${action} Fly.`);
      }
    } catch (caught) {
      setError(getErrorMessage(caught, `Could not ${action} Fly.`));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--panel-line)] bg-[var(--panel)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <span
            aria-hidden="true"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)] text-[var(--accent)]"
          >
            <BrainCircuit className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="text-[0.9375rem] font-medium text-[var(--text-primary)]">
              Fly 3D engine
            </p>
            <p className="mt-1 text-[0.875rem] leading-6 text-[var(--text-secondary)]">
              The behaviour engine behind the 3D connectome view. It runs on its
              own port and is optional: the map, Chat and the Brain all work
              without it.
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span
            className={
              status.reachable
                ? "inline-flex items-center gap-1.5 rounded-full border border-[var(--success)]/40 bg-[var(--success)]/10 px-2.5 py-1 text-[0.75rem] font-semibold text-[var(--success)]"
                : "inline-flex items-center gap-1.5 rounded-full border border-[var(--warning)]/40 bg-[var(--warning)]/10 px-2.5 py-1 text-[0.75rem] font-semibold text-[var(--warning)]"
            }
          >
            <span
              aria-hidden="true"
              className={
                status.reachable
                  ? "h-1.5 w-1.5 rounded-full bg-[var(--success)]"
                  : "h-1.5 w-1.5 rounded-full bg-[var(--warning)]"
              }
            />
            {status.reachable ? "Running" : "Not running"}
          </span>
          <button
            type="button"
            onClick={() => void run(status.reachable ? "stop" : "start")}
            disabled={busy}
            className="min-h-9 rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)] px-3 py-1.5 text-[0.875rem] font-medium text-[var(--text-primary)] transition hover:border-[var(--accent)]/50 hover:text-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Working…" : status.reachable ? "Stop" : "Start"}
          </button>
        </div>
      </div>

      <dl className="mt-4 grid gap-x-6 gap-y-2 border-t border-[var(--panel-line)] pt-3 text-[0.8125rem] sm:grid-cols-2">
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-muted)]">Address</dt>
          <dd className="font-mono text-[var(--text-secondary)]">{status.origin}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-muted)]">Service</dt>
          <dd className="font-mono text-[var(--text-secondary)]">
            {status.service ?? "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-muted)]">Neurons</dt>
          <dd className="font-mono text-[var(--text-secondary)]">
            {status.neurons === null ? "—" : status.neurons.toLocaleString("en-US")}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-[var(--text-muted)]">Flight mode</dt>
          <dd className="font-mono text-[var(--text-secondary)]">
            {status.flightMode === null ? "—" : status.flightMode ? "On" : "Off"}
          </dd>
        </div>
      </dl>

      {!status.reachable && status.error ? (
        <p className="mt-3 text-[0.8125rem] text-[var(--text-muted)]">
          Last probe: {status.error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="mt-3 text-[0.8125rem] text-[var(--success)]">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-3 text-[0.8125rem] text-[var(--danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
