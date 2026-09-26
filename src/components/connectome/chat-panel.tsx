"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BrainCircuit,
  CornerDownLeft,
  LoaderCircle,
  Send,
  Sparkles,
  User2,
} from "lucide-react";
import { ErrorBanner, cn } from "@/components/ui";

/**
 * The Brain's own answer, with the evidence it was built from.
 *
 * Everything rendered here comes from the Brain's `ChatResultWire`: the answer
 * text, the provider that produced it, its confidence, the memories it leaned
 * on, and — when no model was available — the reason. No summary is written on
 * this side, and nothing is filled in when a field is missing. If the Brain
 * degraded, the panel says so rather than dressing a fallback up as a real
 * answer.
 */

interface Grounding {
  memory_id: string;
  type: string;
  content: string;
  content_truncated: boolean;
  score: number;
}

interface ChatResult {
  answer: string;
  message: string;
  user_id: string;
  session_id: string | null;
  provider: string;
  confidence: number;
  fallback_used: boolean;
  fallback_reason: string | null;
  context_fact_count: number;
  grounded_in: Grounding[];
  missing_context: string[];
  learning_recorded: number;
}

interface Turn {
  id: string;
  question: string;
  contextLabel: string | null;
  status: "pending" | "done" | "failed";
  result?: ChatResult;
  error?: string;
}

const SUGGESTIONS = [
  "What do I know about the hackathon?",
  "Who is helping me, and what should I follow up on?",
  "What is connected to this?",
];

function confidenceTone(value: number): string {
  if (value >= 0.75) return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  if (value >= 0.5) return "border-cyan-400/25 bg-cyan-400/10 text-cyan-200";
  if (value > 0) return "border-amber-400/25 bg-amber-400/10 text-amber-200";
  return "border-slate-700 bg-slate-800/70 text-slate-400";
}

export function ChatPanel({
  initialContext,
}: {
  /** A label for whatever the reader was looking at, offered as context. */
  initialContext?: string | null;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [context, setContext] = useState<string | null>(initialContext ?? null);
  const [busy, setBusy] = useState(false);
  const [transportError, setTransportError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || busy) return;

      const turn: Turn = {
        id: `turn-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        question: text,
        contextLabel: context,
        status: "pending",
      };
      setTurns((current) => [...current, turn]);
      setDraft("");
      setTransportError(null);
      setBusy(true);

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            message: text,
            ...(context ? { contextLabel: context } : {}),
          }),
        });
        const body = (await response.json().catch(() => null)) as
          | { data?: BrainEnvelope; error?: { message?: string } }
          | null;

        if (!response.ok || !body?.data) {
          const message =
            body?.error?.message ??
            `The request failed with HTTP ${response.status}.`;
          setTurns((current) =>
            current.map((item) =>
              item.id === turn.id
                ? { ...item, status: "failed" as const, error: message }
                : item,
            ),
          );
          return;
        }

        const envelope = body.data;
        if (envelope.ok === false) {
          setTurns((current) =>
            current.map((item) =>
              item.id === turn.id
                ? {
                    ...item,
                    status: "failed" as const,
                    error: envelope.error?.message ?? "The Brain rejected the question.",
                  }
                : item,
            ),
          );
          return;
        }

        setTurns((current) =>
          current.map((item) =>
            item.id === turn.id
              ? { ...item, status: "done" as const, result: envelope.result as ChatResult }
              : item,
          ),
        );
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "The chat request could not be completed.";
        setTurns((current) =>
          current.map((item) =>
            item.id === turn.id
              ? { ...item, status: "failed" as const, error: message }
              : item,
          ),
        );
        setTransportError(message);
      } finally {
        setBusy(false);
        inputRef.current?.focus();
      }
    },
    [busy, context],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
        {turns.length === 0 ? (
          <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-10 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
              <BrainCircuit aria-hidden="true" className="h-5 w-5" />
            </span>
            <h2 className="mt-4 text-base font-semibold text-slate-100">
              Ask your brain
            </h2>
            <p className="mt-1.5 max-w-md text-sm leading-6 text-slate-400">
              Answers come from the memories the Core Brain stored on this
              device. It cites what it used, and says so when it could not
              reach a model.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void send(suggestion)}
                  className="rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300 transition hover:border-cyan-400/30 hover:text-cyan-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto w-full max-w-2xl space-y-5">
            {turns.map((turn) => (
              <TurnCard key={turn.id} turn={turn} />
            ))}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-slate-800/70 bg-zinc-950/70 px-4 py-3 sm:px-6">
        <div className="mx-auto w-full max-w-2xl">
          {context ? (
            <div className="mb-2 flex items-center gap-2 text-[11px] text-slate-500">
              <span className="truncate">
                Context: <span className="text-slate-400">{context}</span>
              </span>
              <button
                type="button"
                onClick={() => setContext(null)}
                className="shrink-0 rounded px-1 text-slate-500 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                clear
              </button>
            </div>
          ) : null}

          {transportError ? (
            <div className="mb-2">
              <ErrorBanner
                title="The Brain could not be reached"
                message={transportError}
                onRetry={() => {
                  setTransportError(null);
                  void send(turns[turns.length - 1]?.question ?? draft);
                }}
              />
            </div>
          ) : null}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              void send(draft);
            }}
            className="flex items-end gap-2"
          >
            <label htmlFor="chat-input" className="sr-only">
              Ask the Core Brain a question
            </label>
            <textarea
              id="chat-input"
              ref={inputRef}
              rows={2}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send(draft);
                }
              }}
              placeholder="What do I know about…"
              className="min-h-11 flex-1 resize-none rounded-xl border border-slate-700/80 bg-slate-950/70 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 hover:border-slate-600 focus:border-cyan-400/70 focus:ring-2 focus:ring-cyan-400/20"
            />
            <button
              type="submit"
              disabled={busy || draft.trim().length === 0}
              aria-label="Send question"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-cyan-300 text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
            >
              {busy ? (
                <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <Send aria-hidden="true" className="h-4 w-4" />
              )}
            </button>
          </form>
          <p className="mt-2 text-[11px] text-slate-600">
            <CornerDownLeft aria-hidden="true" className="mr-1 inline h-3 w-3" />
            Enter to send, Shift+Enter for a new line. Answers come only from stored
            memory.
          </p>
        </div>
      </div>
    </div>
  );
}

function TurnCard({ turn }: { turn: Turn }) {
  return (
    <article className="space-y-3">
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400">
          <User2 aria-hidden="true" className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm text-slate-200">{turn.question}</p>
          {turn.contextLabel ? (
            <p className="mt-0.5 truncate text-[11px] text-slate-600">
              while looking at {turn.contextLabel}
            </p>
          ) : null}
        </div>
      </div>

      <div className="ml-9 space-y-3">
        {turn.status === "pending" ? (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <LoaderCircle aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
            Thinking…
          </p>
        ) : null}

        {turn.status === "failed" ? (
          <ErrorBanner title="The Brain could not answer" message={turn.error ?? ""} />
        ) : null}

        {turn.status === "done" && turn.result ? (
          <AnswerPanel result={turn.result} />
        ) : null}
      </div>
    </article>
  );
}

function AnswerPanel({ result }: { result: ChatResult }) {
  const grounding = result.grounded_in ?? [];
  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
        <p className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-100">
          {result.answer}
        </p>

        <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-slate-800/70 pt-3">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold",
              confidenceTone(result.confidence),
            )}
          >
            <Sparkles aria-hidden="true" className="h-3 w-3" />
            Confidence {(result.confidence ?? 0).toFixed(2)}
          </span>
          <span className="inline-flex items-center rounded-full border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-[11px] text-slate-300">
            {result.provider}
          </span>
          <span className="text-[11px] text-slate-500">
            {result.context_fact_count} fact
            {result.context_fact_count === 1 ? "" : "s"} in context
          </span>
        </div>

        {result.fallback_used ? (
          <p className="mt-3 flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.07] px-3 py-2 text-[11px] leading-5 text-amber-100">
            <AlertTriangle aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              No model answered this — the Brain replied from its own memory
              only.
              {result.fallback_reason ? ` (${result.fallback_reason})` : ""}
            </span>
          </p>
        ) : null}
      </div>

      {grounding.length > 0 ? (
        <div className="rounded-2xl border border-slate-800/80 bg-slate-900/30 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Grounded in {grounding.length} memor
            {grounding.length === 1 ? "y" : "ies"}
          </p>
          <ul className="mt-2.5 space-y-2">
            {grounding.map((item) => (
              <li
                key={item.memory_id}
                className="rounded-lg border border-slate-800/80 bg-slate-950/40 px-3 py-2"
              >
                <p className="break-words text-xs leading-5 text-slate-300">
                  {item.content}
                  {item.content_truncated ? "…" : ""}
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-600">
                  <span className="font-mono">{item.memory_id}</span>
                  <span>score {item.score.toFixed(2)}</span>
                  <span>{item.type}</span>
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-[11px] text-slate-600">
          No memories were used for this answer.
        </p>
      )}

      {result.missing_context?.length ? (
        <p className="text-[11px] leading-5 text-slate-500">
          The Brain reported that it is still missing:{" "}
          {result.missing_context.join(", ")}.
        </p>
      ) : null}
    </div>
  );
}

interface BrainEnvelope {
  ok: boolean;
  result: unknown;
  error?: { code?: string; message?: string } | null;
}

export function ChatPageHeader() {
  return (
    <div className="flex flex-col gap-4 border-b border-slate-800/80 px-4 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-6">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300">
          Intelligence
        </p>
        <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-white sm:text-2xl">
          Ask the brain
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-400">
          Questions are answered by the Core Brain from memory it stored on this
          device. Every answer shows its confidence and the memories behind it.
        </p>
      </div>
      <Link
        href="/connectome"
        className="shrink-0 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-slate-600 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
      >
        See it on the Connectome
      </Link>
    </div>
  );
}
