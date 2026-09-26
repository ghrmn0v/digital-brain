"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Brain as BrainIcon,
  Check,
  ChevronRight,
  CircleAlert,
  Search,
  Send,
  Sparkles,
  UserRound,
} from "@/components/icons";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  Badge,
  ButtonSpinner,
  EmptyState,
  ErrorBanner,
  Panel,
  SectionHeading,
  StatusBadge,
  inputClassName,
  primaryButtonClassName,
  secondaryButtonClassName,
} from "@/components/ui";
import { JsonViewer } from "@/components/json-viewer";
import type { BrainStatusDto } from "@/modules/brain/contracts";

const GROUP_LABELS: Record<string, string> = {
  converse: "Converse",
  understand: "Understand & reason",
  memory: "Memory",
  people: "People",
  preferences: "Preferences & learning",
  developer: "Developer",
  ingest: "Ingest",
  system: "System",
};

const GROUP_ORDER = [
  "converse",
  "understand",
  "memory",
  "people",
  "preferences",
  "developer",
  "ingest",
  "system",
];

interface CallResult {
  ok: boolean;
  data: unknown;
  error: string | null;
  code: string | null;
}

export function BrainConsole({ status }: { status: BrainStatusDto }) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState<CallResult | null>(null);
  const [searchText, setSearchText] = useState("");
  const [searchResult, setSearchResult] = useState<CallResult | null>(null);
  const [personName, setPersonName] = useState("");
  const [personResult, setPersonResult] = useState<CallResult | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    return GROUP_ORDER.map((group) => ({
      group,
      label: GROUP_LABELS[group],
      items: status.capabilities.filter((c) => c.group === group),
    })).filter((section) => section.items.length > 0);
  }, [status.capabilities]);

  const invoke = useCallback(
    async (
      key: string,
      method: string,
      input: Record<string, unknown>,
      onDone: (result: CallResult) => void,
    ) => {
      setPending(key);
      setError(null);
      try {
        onDone(
          await apiRequest<CallResult>("/api/brain/call", {
            method: "POST",
            body: { method, input },
          }),
        );
        router.refresh();
      } catch (caught) {
        setError(getErrorMessage(caught, "Core Brain call failed."));
      } finally {
        setPending(null);
      }
    },
    [router],
  );

  const disabled = !status.reachable;

  return (
    <div className="space-y-6">
      <Panel>
        <SectionHeading
          title="Ask the Brain"
          description="Answers grounded in memory, with optional learning"
          action={
            <Badge tone={disabled ? "neutral" : "success"} dot>
              {status.provider ?? (disabled ? "Offline" : "Connected")}
            </Badge>
          }
        />
        <div className="space-y-4 p-5">
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              className={inputClassName}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="What do you remember about my work?"
              maxLength={8000}
              disabled={disabled || pending === "chat"}
            />
            <button
              type="button"
              className={`${primaryButtonClassName} sm:w-auto`}
              disabled={disabled || pending === "chat" || !message.trim()}
              onClick={() =>
                void invoke(
                  "chat",
                  "chat",
                  { message: message.trim() },
                  (result) => {
                    setAnswer(result);
                    if (result.ok) setMessage("");
                  },
                )
              }
            >
              {pending === "chat" ? <ButtonSpinner /> : <Send aria-hidden="true" className="h-4 w-4" />}
              Ask
            </button>
          </div>

          {answer ? (
            <BrainAnswer result={answer} />
          ) : (
            <p className="text-xs text-[var(--text-muted)]">
              The Brain answers only from stored memory. Anything it does not know is
              reported as missing rather than invented.
            </p>
          )}
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <SectionHeading
            title="Search memory"
            description="Ranked retrieval across everything the Brain has stored"
            action={<Search aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />}
          />
          <div className="space-y-4 p-5">
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                className={inputClassName}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="deadline, ayxan, deploy…"
                maxLength={2000}
                disabled={disabled || pending === "search"}
              />
              <button
                type="button"
                className={secondaryButtonClassName}
                disabled={disabled || pending === "search" || !searchText.trim()}
                onClick={() =>
                  void invoke(
                    "search",
                    "search",
                    { text: searchText.trim(), limit: 10 },
                    setSearchResult,
                  )
                }
              >
                {pending === "search" ? <ButtonSpinner /> : null}
                Search
              </button>
            </div>
            {searchResult ? <BrainAnswer result={searchResult} /> : null}
          </div>
        </Panel>

        <Panel>
          <SectionHeading
            title="Resolve a person"
            description="Resolve a name. Ambiguous names are never merged"
            action={<UserRound aria-hidden="true" className="h-4 w-4 text-emerald-300" />}
          />
          <div className="space-y-4 p-5">
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                className={inputClassName}
                value={personName}
                onChange={(e) => setPersonName(e.target.value)}
                placeholder="Ayxan"
                maxLength={200}
                disabled={disabled || pending === "person"}
              />
              <button
                type="button"
                className={secondaryButtonClassName}
                disabled={disabled || pending === "person" || !personName.trim()}
                onClick={() =>
                  void invoke(
                    "person",
                    "resolve_person",
                    { name: personName.trim() },
                    (result) => {
                      setPersonResult(result);
                      if (result.ok) setPersonName("");
                    },
                  )
                }
              >
                {pending === "person" ? <ButtonSpinner /> : null}
                Resolve
              </button>
            </div>
            {personResult ? <BrainAnswer result={personResult} /> : null}
          </div>
        </Panel>
      </div>

      {error ? <ErrorBanner title="Core Brain call failed" message={error} /> : null}

      <Panel>
        <SectionHeading
          title="Capability catalogue"
          description={`${status.methodCount || status.capabilities.length} methods on the Core Brain API v1`}
          action={
            <span className="text-xs text-[var(--text-muted)]">
              Product holds no intelligence — every result below is the Brain&apos;s own
            </span>
          }
        />
        {grouped.length > 0 ? (
          <div className="divide-y divide-slate-800/70">
            {grouped.map((section) => (
              <div key={section.group} className="px-5 py-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
                  {section.label}
                </p>
                <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                  {section.items.map((capability) => (
                    <li
                      key={capability.method}
                      className="flex items-start gap-3 rounded-lg border border-[var(--panel-line)]/70 bg-[#1a1a1a]/40 px-3 py-2.5"
                    >
                      <ChevronRight
                        aria-hidden="true"
                        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <code className="text-xs font-semibold text-[var(--accent)]">
                            {capability.method}
                          </code>
                          {capability.interactive ? (
                            <StatusBadge status="interactive" />
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
                          {capability.summary}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={BrainIcon}
            title="No capabilities"
            description="Core Brain did not report any methods."
          />
        )}
      </Panel>
    </div>
  );
}

function BrainAnswer({ result }: { result: CallResult }) {
  if (!result.ok) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-rose-500/25 bg-rose-500/5 p-4">
        <CircleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-rose-200">
            {result.code ?? "error"}
          </p>
          <p className="mt-1 break-words text-sm text-[var(--text-secondary)]">{result.error}</p>
        </div>
      </div>
    );
  }

  const data = result.data as Record<string, unknown> | null;
  const answer = typeof data?.answer === "string" ? data.answer : null;
  const confidence = typeof data?.confidence === "number" ? data.confidence : null;
  const provider = typeof data?.provider === "string" ? data.provider : null;
  const grounded = Array.isArray(data?.grounded_in) ? data.grounded_in : [];
  const missing = Array.isArray(data?.missing_context) ? data.missing_context : [];

  if (answer) {
    return (
      <div className="space-y-3 rounded-lg border border-sky-500/20 bg-sky-500/[0.04] p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
          <Sparkles aria-hidden="true" className="h-3.5 w-3.5 text-[var(--accent)]" />
          {provider ? <span>provider: {provider}</span> : null}
          {confidence !== null ? (
            <span>confidence: {confidence.toFixed(2)}</span>
          ) : null}
          {Array.isArray(data?.fallback_used) && data.fallback_used ? (
            <Badge tone="warning">fallback</Badge>
          ) : null}
        </div>
        <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-primary)]">{answer}</p>
        {grounded.length > 0 ? (
          <div className="border-t border-[var(--panel-line)] pt-3 text-xs text-[var(--text-muted)]">
            Grounded in {grounded.length} memory record
            {grounded.length === 1 ? "" : "s"}
          </div>
        ) : null}
        {missing.length > 0 ? (
          <div className="border-t border-[var(--panel-line)] pt-3 text-xs text-[var(--text-muted)]">
            <span className="font-semibold text-amber-300/90">Not in memory: </span>
            {missing.join(", ")}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--panel-line)] bg-[#1a1a1a]/40 p-3">
      {Array.isArray(data) ? (
        data.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
            <Check aria-hidden="true" className="h-4 w-4 text-emerald-300" />
            No matching records.
          </p>
        ) : (
          <div className="space-y-2">
            {data.map((hit, index) => {
              const record = hit as Record<string, unknown>;
              return (
                <div
                  key={String(record.memory_id ?? index)}
                  className="rounded-lg border border-[var(--panel-line)]/70 px-3 py-2"
                >
                  <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-muted)]">
                    <code className="text-[var(--accent)]/80">{String(record.type)}</code>
                    <span>score {Number(record.score ?? 0).toFixed(3)}</span>
                    {typeof record.ranking_reason === "string" ? (
                      <span className="truncate">{record.ranking_reason}</span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-primary)]">
                    {String(record.content ?? "")}
                  </p>
                </div>
              );
            })}
          </div>
        )
      ) : (
        <JsonViewer value={data} />
      )}
    </div>
  );
}
