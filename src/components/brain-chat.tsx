"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  CircleAlert,
  Info,
  MagnifyingGlass,
  Motor,
  Sparkle,
  SpinnerGap,
  UserCircle,
} from "@/components/icons";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  ButtonSpinner,
  ErrorBanner,
  inputClassName,
  primaryButtonClassName,
  secondaryButtonClassName,
} from "@/components/ui";
import type { BrainStatusDto } from "@/modules/brain/contracts";

interface CallResult {
  ok: boolean;
  data: unknown;
  error: string | null;
  code: string | null;
}

interface Turn {
  id: string;
  role: "user" | "brain";
  text: string;
  meta?: BrainMeta;
  failed?: boolean;
}

interface BrainMeta {
  provider: string | null;
  confidence: number | null;
  grounded: number;
  missing: string[];
  fallback: boolean;
}

const SUGGESTIONS = [
  "What do you remember about my work?",
  "Who are the people I work with?",
  "What tasks are waiting for me?",
];

function readMeta(data: unknown): BrainMeta {
  const record = (data ?? {}) as Record<string, unknown>;
  return {
    provider: typeof record.provider === "string" ? record.provider : null,
    confidence:
      typeof record.confidence === "number" ? record.confidence : null,
    grounded: Array.isArray(record.grounded_in) ? record.grounded_in.length : 0,
    missing: Array.isArray(record.missing_context)
      ? record.missing_context.map(String)
      : [],
    fallback: record.fallback_used === true,
  };
}

export function BrainChat({ status }: { status: BrainStatusDto }) {
  const router = useRouter();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const offline = !status.reachable;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns, pending]);

  const send = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || pending) return;

      setTurns((current) => [
        ...current,
        { id: `u-${Date.now()}`, role: "user", text: trimmed },
      ]);
      setDraft("");
      setPending(true);
      setError(null);

      try {
        const result = await apiRequest<CallResult>("/api/brain/call", {
          method: "POST",
          body: {
            method: "chat",
            input: { message: trimmed, ...(sessionId ? { sessionId } : {}) },
          },
        });

        if (result.ok) {
          const data = result.data as Record<string, unknown>;
          const answer =
            typeof data?.answer === "string" && data.answer.length > 0
              ? data.answer
              : "The Brain returned no answer.";
          const nextSession =
            typeof data?.session_id === "string" ? data.session_id : sessionId;
          if (nextSession) setSessionId(nextSession);

          setTurns((current) => [
            ...current,
            {
              id: `b-${Date.now()}`,
              role: "brain",
              text: answer,
              meta: readMeta(result.data),
            },
          ]);
        } else {
          setTurns((current) => [
            ...current,
            {
              id: `e-${Date.now()}`,
              role: "brain",
              text: result.error ?? "The Brain could not answer.",
              failed: true,
            },
          ]);
        }
        router.refresh();
      } catch (caught) {
        setError(getErrorMessage(caught, "Could not reach Core Brain."));
      } finally {
        setPending(false);
      }
    },
    [pending, router, sessionId],
  );

  const empty = turns.length === 0;

  return (
    <section className="overflow-hidden rounded-lg border border-[var(--panel-line)]/80 bg-[var(--panel)]/40">
      {/* Conversation */}
      <div
        ref={scrollRef}
        className="max-h-[32rem] min-h-[18rem] space-y-7 overflow-y-auto px-6 py-8"
      >
        {empty ? (
          <div className="flex h-full flex-col items-start justify-center gap-6">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-sky-400/25 bg-sky-400/10 text-[var(--accent)]">
              <Motor aria-hidden="true" className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-[1.25rem] font-semibold text-[var(--text-primary)]">
                Ask the Brain
              </h2>
              <p className="mt-2 max-w-prose text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
                Answers come only from stored memory. Anything the Brain does
                not know is reported as missing, never invented.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={offline || pending}
                  onClick={() => void send(suggestion)}
                  className={secondaryButtonClassName}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          turns.map((turn) => (
            <Message key={turn.id} turn={turn} />
          ))
        )}

        {pending ? (
          <div className="flex items-center gap-3 text-[var(--text-secondary)]">
            <Sparkle aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />
            <span className="text-[0.9375rem]">Thinking…</span>
            <SpinnerGap aria-hidden="true" className="h-4 w-4 animate-spin" />
          </div>
        ) : null}
      </div>

      {/* Composer */}
      <div className="border-t border-[var(--panel-line)]/70 px-6 py-5">
        {error ? (
          <div className="mb-4">
            <ErrorBanner title="Core Brain unreachable" message={error} />
          </div>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send(draft);
          }}
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <div className="relative flex-1">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask based on stored memory…"
              maxLength={8000}
              disabled={offline || pending}
              aria-label="Ask the Brain a question"
              className={inputClassName}
            />
            <Info
              aria-hidden="true"
              className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]"
            />
          </div>
          <button
            type="submit"
            disabled={offline || pending || !draft.trim()}
            className={`${primaryButtonClassName} sm:h-12 sm:px-6`}
          >
            {pending ? <ButtonSpinner /> : <ArrowUp aria-hidden="true" className="h-4 w-4" />}
            Ask
          </button>
        </form>

        {offline ? (
          <p className="mt-3 text-[0.8125rem] text-[var(--text-muted)]">
            Core Brain is offline. Start it on port 8765 to chat.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function Message({ turn }: { turn: Turn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-sky-400/10 px-4 py-3 text-[0.9375rem] leading-7 text-sky-50">
          <p className="whitespace-pre-wrap">{turn.text}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-sky-400/20 bg-sky-400/10 text-[var(--accent)]">
        {turn.failed ? (
          <CircleAlert aria-hidden="true" className="h-4 w-4 text-rose-300" />
        ) : (
          <Motor aria-hidden="true" className="h-4 w-4" />
        )}
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        <p
          className={`whitespace-pre-wrap text-[0.9375rem] leading-8 ${
            turn.failed ? "text-rose-200" : "text-[var(--text-primary)]"
          }`}
        >
          {turn.text}
        </p>
        {turn.meta ? <MetaRow meta={turn.meta} /> : null}
      </div>
    </div>
  );
}

function MetaRow({ meta }: { meta: BrainMeta }) {
  const chips: string[] = [];
  if (meta.provider) chips.push(meta.provider);
  if (meta.confidence !== null) chips.push(`confidence ${meta.confidence.toFixed(2)}`);
  if (meta.grounded > 0) {
    chips.push(`${meta.grounded} memory record${meta.grounded === 1 ? "" : "s"}`);
  }
  if (meta.fallback) chips.push("fallback");

  return (
    <div className="space-y-2 border-t border-[var(--panel-line)]/60 pt-3">
      {chips.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {chips.map((chip) => (
            <span
              key={chip}
              className="rounded-full border border-[var(--panel-line)]/80 bg-[var(--panel-raised)] px-2.5 py-1 text-[0.75rem] text-[var(--text-secondary)]"
            >
              {chip}
            </span>
          ))}
        </div>
      ) : null}
      {meta.missing.length > 0 ? (
        <p className="text-[0.8125rem] leading-6 text-amber-300/80">
          Not in memory: {meta.missing.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

/** Secondary tools. Deliberately quieter than the chat. */
export function BrainTools({ status }: { status: BrainStatusDto }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [searchResult, setSearchResult] = useState<CallResult | null>(null);
  const [personResult, setPersonResult] = useState<CallResult | null>(null);
  const [pending, setPending] = useState<"search" | "person" | null>(null);

  const offline = !status.reachable;

  const run = async (
    key: "search" | "person",
    method: string,
    input: Record<string, unknown>,
    set: (value: CallResult) => void,
    clear: () => void,
  ) => {
    setPending(key);
    try {
      set(
        await apiRequest<CallResult>("/api/brain/call", {
          method: "POST",
          body: { method, input },
        }),
      );
      clear();
      router.refresh();
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Tool
        title="Search memory"
        description="Ranked retrieval across everything stored"
        icon={MagnifyingGlass}
        value={query}
        onChange={setQuery}
        placeholder="deadline, ayxan, deploy…"
        action="Search"
        disabled={offline}
        pending={pending === "search"}
        onSubmit={() =>
          void run(
            "search",
            "search",
            { text: query.trim(), limit: 10 },
            setSearchResult,
            () => setQuery(""),
          )
        }
        result={searchResult}
      />
      <Tool
        title="Resolve a person"
        description="Ambiguous names are never merged"
        icon={UserCircle}
        value={name}
        onChange={setName}
        placeholder="Ayxan"
        action="Resolve"
        disabled={offline}
        pending={pending === "person"}
        onSubmit={() =>
          void run(
            "person",
            "resolve_person",
            { name: name.trim() },
            setPersonResult,
            () => setName(""),
          )
        }
        result={personResult}
      />
    </div>
  );
}

function Tool({
  title,
  description,
  icon: Icon,
  value,
  onChange,
  placeholder,
  action,
  disabled,
  pending,
  onSubmit,
  result,
}: {
  title: string;
  description: string;
  icon: typeof MagnifyingGlass;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  action: string;
  disabled: boolean;
  pending: boolean;
  onSubmit: () => void;
  result: CallResult | null;
}) {
  return (
    <section className="rounded-lg border border-[var(--panel-line)]/80 bg-[var(--panel)]/40 p-6">
      <div className="flex items-center gap-3">
        <Icon aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />
        <div>
          <h3 className="text-[1.0625rem] font-semibold text-[var(--text-primary)]">{title}</h3>
          <p className="mt-0.5 text-[0.8125rem] text-[var(--text-muted)]">{description}</p>
        </div>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        className="mt-5 flex gap-3"
      >
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          maxLength={2000}
          disabled={disabled || pending}
          aria-label={title}
          className={inputClassName}
        />
        <button
          type="submit"
          disabled={disabled || pending || !value.trim()}
          className={`${secondaryButtonClassName} shrink-0`}
        >
          {pending ? <ButtonSpinner /> : null}
          {action}
        </button>
      </form>

      {result ? <ToolResult result={result} /> : null}
    </section>
  );
}

function ToolResult({ result }: { result: CallResult }) {
  if (!result.ok) {
    return (
      <p className="mt-5 rounded-lg border border-rose-400/25 bg-rose-400/5 px-4 py-3 text-[0.9375rem] text-rose-200">
        {result.error}
      </p>
    );
  }

  const data = result.data as Record<string, unknown> | null;
  const items = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : null;

  if (items) {
    if (items.length === 0) {
      return (
        <p className="mt-5 text-[0.9375rem] text-[var(--text-muted)]">No matching records.</p>
      );
    }
    return (
      <ul className="mt-5 space-y-3">
        {items.map((item, index) => {
          const record = item as Record<string, unknown>;
          return (
            <li key={String(record.memory_id ?? record.person_id ?? index)}>
              <div className="flex flex-wrap items-center gap-2 text-[0.75rem] text-[var(--text-muted)]">
                <span className="rounded-full border border-[var(--panel-line)]/80 bg-[var(--panel-raised)] px-2 py-0.5">
                  {String(record.type ?? "record")}
                </span>
                {typeof record.score === "number" ? (
                  <span>score {record.score.toFixed(3)}</span>
                ) : null}
                {typeof record.person_id === "string" ? (
                  <span className="font-mono">{record.person_id}</span>
                ) : null}
              </div>
              <p className="mt-1.5 text-[0.9375rem] leading-7 text-[var(--text-primary)]">
                {String(record.content ?? record.name ?? "")}
              </p>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <div className="mt-5 space-y-2 text-[0.9375rem] text-[var(--text-primary)]">
      {typeof data?.person_id === "string" ? (
        <p className="font-mono text-[var(--accent)]">{data.person_id}</p>
      ) : null}
      {typeof data?.known === "boolean" ? (
        <p className="text-[var(--text-secondary)]">
          {data.known ? "Identity resolved." : "No unambiguous match — nothing merged."}
        </p>
      ) : null}
    </div>
  );
}

