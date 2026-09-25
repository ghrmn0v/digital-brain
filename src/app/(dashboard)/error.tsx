"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

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
      className="flex min-h-[60vh] items-center justify-center rounded-2xl border border-rose-400/20 bg-rose-500/[0.06] p-6"
    >
      <div className="max-w-lg text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-rose-400/20 bg-rose-400/10 text-rose-200">
          <AlertTriangle aria-hidden="true" className="h-6 w-6" />
        </div>
        <h1 className="mt-5 text-xl font-semibold text-white">
          This dashboard view could not be loaded
        </h1>
        <p className="mt-2 text-sm leading-6 text-rose-100/70">
          The local data service returned an unexpected error. Your data was not
          changed.
        </p>
        {error.digest ? (
          <p className="mt-2 font-mono text-[11px] text-rose-200/50">
            Reference: {error.digest}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          className="mt-6 inline-flex min-h-10 items-center gap-2 rounded-xl border border-rose-300/20 bg-rose-400/10 px-4 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-400/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/50"
        >
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          Try again
        </button>
      </div>
    </div>
  );
}
