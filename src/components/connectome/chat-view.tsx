"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { BrainCircuit } from "lucide-react";
import { ChatPageHeader, ChatPanel } from "@/components/connectome/chat-panel";

/**
 * The Chat surface.
 *
 * It deliberately reuses the Connectome's frame — same ground, same drawer
 * breakpoints, same drawer treatment — so it reads as the same application
 * rather than a separate product bolted on. A `?context=` query parameter
 * carries whatever the reader was looking at, which is how a node selected in
 * the graph becomes a question with context.
 */

function ContextFromQuery() {
  const params = useSearchParams();
  const raw = params.get("context");
  const context = raw && raw.trim() ? raw.trim().slice(0, 200) : null;
  return <ChatPanel initialContext={context} />;
}

export function ChatView() {
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[var(--background)] text-[var(--text-primary)]">
      <a
        href="#chat-input"
        className="fixed left-3 top-3 z-[130] -translate-y-20 rounded-lg border border-cyan-300/30 bg-[var(--panel)] px-4 py-2 text-sm font-semibold text-cyan-100 transition focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
      >
        Skip to the question box
      </a>

      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[var(--panel-line)]/70 bg-[var(--background)]/92 px-3 backdrop-blur-xl sm:px-4">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
          <BrainCircuit aria-hidden="true" className="h-3.5 w-3.5" />
        </span>
        <span className="text-[13px] font-semibold tracking-tight text-white">
          Cerebro Flow
        </span>
        <div className="ml-auto flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
          <span className="hidden sm:inline">Grounded in stored memory</span>
        </div>
      </header>

      <ChatPageHeader />

      <main id="main-content" className="flex min-h-0 flex-1 flex-col">
        <Suspense
          fallback={
            <p className="px-6 py-8 text-center text-sm text-[var(--text-secondary)]">
              Loading the question box…
            </p>
          }
        >
          <ContextFromQuery />
        </Suspense>
      </main>
    </div>
  );
}
