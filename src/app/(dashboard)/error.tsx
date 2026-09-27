"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "@/components/icons";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard route failed.", error);
  }, [error]);

  return (
    <div
      role="alert"
      className="flex min-h-[60vh] items-center justify-center rounded-lg border border-[var(--danger)]/20 bg-[var(--danger)]/[0.06] p-6"
    >
      <div className="max-w-lg">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg border border-[var(--danger)]/20 bg-[var(--danger)]/10 text-[var(--danger)]">
          <AlertTriangle aria-hidden="true" className="h-6 w-6" />
        </div>
        <h1 className="mt-5 text-xl font-semibold text-[var(--text-primary)]">
          This dashboard view could not be loaded
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--danger)]/70">
          The local data service returned an unexpected error. Your data was not
          changed.
        </p>
        {error.digest ? (
          <p className="mt-2 font-mono text-[11px] text-[var(--danger)]/50">
            Reference: {error.digest}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-lg border border-[var(--danger)]/20 bg-[var(--danger)]/10 px-4 py-2 text-sm font-semibold text-[var(--danger)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--danger)]/50"
        >
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          Try again
        </button>
      </div>
    </div>
  );
}
