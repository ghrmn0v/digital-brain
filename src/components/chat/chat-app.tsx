"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
  BrainCircuit,
  Code2,
  MagnifyingGlass,
  Microphone,
  Motor,
  Paperclip,
  PaperPlaneTilt,
  Sparkle,
  SpinnerGap,
  Star,
  Trash,
  UserCircle,
} from "@/components/icons";
import Link from "next/link";
import { AppMenu } from "@/components/chat/app-menu";
import { CerebroLogo, CerebroMark } from "@/components/brand/cerebro-logo";
import { BrainIdleView } from "@/components/chat/brain-idle-view";
import { ThemeToggle } from "@/components/chat/theme-toggle";
import { apiRequest, getErrorMessage } from "@/lib/client/api";
import {
  deleteConversation,
  getSnapshot,
  newConversation,
  renameFromFirstMessage,
  saveConversation,
  subscribe,
  type ChatMessage,
  type Conversation,
} from "@/lib/chat/history";
import { cn, inputClassName, secondaryButtonClassName } from "@/components/ui";
import type { BrainStatusDto } from "@/modules/brain/contracts";
import { SUPPORTED_SOURCE_EVENTS } from "@/modules/brain/contracts";

const EMPTY_MESSAGES: ChatMessage[] = [];

/*
 * Hydration gate.
 *
 * Conversation history lives in localStorage, which the server cannot read, so
 * the server renders "no chats" and the client renders the real list. Reading
 * this through useSyncExternalStore keeps both sides in agreement on the first
 * paint, and needs no setState inside an effect.
 */
/** Stable empty list so the server and the first client render always agree. */
const NO_CONVERSATIONS: Conversation[] = [];

const noopSubscribe = () => () => {};
const hydratedOnClient = () => true;
const notHydratedOnServer = () => false;

function now(): number {
  return Date.now();
}

function makeId(prefix: string): string {
  return `${prefix}-${now()}-${Math.random().toString(36).slice(2, 8)}`;
}

interface CallResult {
  ok: boolean;
  data: unknown;
  error: string | null;
  code?: string | null;
}

type View = "chat" | "connectome" | "search" | "people" | "learning" | "developer" | "capabilities";

/* One flat list. Grouping headers added noise without adding meaning. */
/*
 * An item is either a local panel in this shell or, when it carries an `href`,
 * a link to a real route. The Connectome is the second kind: it is its own page,
 * and treating it as a local view is how the product-UI merge left it with no
 * navigation entry at all — reachable only by typing the URL.
 */
const VIEWS: { id: View; label: string; icon: typeof Motor; href?: string }[] = [
  { id: "chat", label: "Chat", icon: Motor },
  { id: "connectome", label: "Connectome", icon: BrainCircuit, href: "/connectome" },
  { id: "search", label: "Search", icon: MagnifyingGlass },
  { id: "people", label: "People", icon: UserCircle },
  { id: "learning", label: "Learning", icon: Star },
  { id: "developer", label: "Developer", icon: Code2 },
  { id: "capabilities", label: "Capabilities", icon: Sparkle },
];

export function ChatApp({ status }: { status: BrainStatusDto }) {
  /*
   * The third argument matters: the server has no localStorage, so its snapshot
   * is the empty list. Passing the real snapshot there is what produced the
   * hydration mismatch on the chat history.
   */
  const conversations = useSyncExternalStore(
    subscribe,
    getSnapshot,
    () => NO_CONVERSATIONS,
  );
  const hydrated = useSyncExternalStore(
    noopSubscribe,
    hydratedOnClient,
    notHydratedOnServer,
  );
  const [view, setView] = useState<View>("chat");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draftChat, setDraftChat] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);

  const active = useMemo(() => {
    if (activeId) return conversations.find((item) => item.id === activeId) ?? null;
    return draftChat;
  }, [activeId, conversations, draftChat]);

  const messages = active?.messages ?? EMPTY_MESSAGES;
  const offline = !status.reachable;

  useEffect(() => {
    const node = threadRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, pending]);

  function persist(next: Conversation) {
    const titled = renameFromFirstMessage(next);
    setDraftChat(null);
    saveConversation(titled);
    setActiveId(titled.id);
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || pending) return;

    const base: Conversation = active ?? newConversation();
    const withUser: Conversation = {
      ...base,
      updatedAt: now(),
      messages: [...base.messages, { id: makeId("u"), role: "user", text: question }],
    };

    setDraftChat(withUser);
    setActiveId(null);
    setDraft("");
    setPending(true);
    setError(null);

    try {
      const result = await apiRequest<CallResult>("/api/brain/call", {
        method: "POST",
        body: { method: "chat", input: { message: question } },
      });

      const data = (result.data ?? {}) as Record<string, unknown>;
      const answer =
        typeof data.answer === "string" && data.answer.length > 0
          ? data.answer
          : "The Brain returned no answer.";

      const reply: ChatMessage = result.ok
        ? {
            id: makeId("b"),
            role: "brain",
            text: answer,
            meta: {
              provider: typeof data.provider === "string" ? data.provider : null,
              confidence:
                typeof data.confidence === "number" ? data.confidence : null,
              grounded: Array.isArray(data.grounded_in) ? data.grounded_in.length : 0,
              missing: Array.isArray(data.missing_context)
                ? data.missing_context.map(String)
                : [],
              fallback: data.fallback_used === true,
            },
          }
        : {
            id: makeId("e"),
            role: "brain",
            text: result.error ?? "The Brain could not answer.",
            failed: true,
          };

      persist({
        ...withUser,
        updatedAt: now(),
        messages: [...withUser.messages, reply],
      });
    } catch (caught) {
      setError(getErrorMessage(caught, "Could not reach Core Brain."));
    } finally {
      setPending(false);
    }
  }

  function startNew() {
    setActiveId(null);
    setDraftChat(null);
    setDraft("");
    setError(null);
    setSidebarOpen(false);
  }

  function go(next: View) {
    setView(next);
    setSidebarOpen(false);
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-[var(--background)]">
      {/* ------------------------------ Sidebar ------------------------------ */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[var(--panel-line)] bg-[var(--panel)] transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between gap-2 px-3 py-3">
          <button
            type="button"
            onClick={startNew}
            title="New chat"
            aria-label="New chat"
            className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
          >
            <CerebroLogo />
          </button>
          <button
            type="button"
            onClick={startNew}
            aria-label="New chat"
            className="rounded-lg border border-[var(--panel-line)] p-2 text-[var(--text-secondary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
          >
            <Sparkle aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>

        <nav className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-3 pb-1.5 pt-2 text-[0.75rem] font-medium uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Overview
          </p>
          <ul className="space-y-0.5">
            {VIEWS.map((item) => {
              const Icon = item.icon;
              const selected = view === item.id;
              const className = cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[0.9375rem] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40",
                selected
                  ? "bg-[var(--panel-raised)] text-[var(--text-primary)]"
                  : "text-[var(--text-secondary)]",
              );
              const glyph = (
                <Icon
                  aria-hidden="true"
                  className={cn(
                    "h-4 w-4 shrink-0",
                    selected ? "text-[var(--accent)]" : "text-[var(--text-muted)]",
                  )}
                />
              );
              return (
                <li key={item.id}>
                  {item.href ? (
                    <Link href={item.href} className={className}>
                      {glyph}
                      {item.label}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      onClick={() => go(item.id)}
                      aria-current={selected ? "page" : undefined}
                      className={className}
                    >
                      {glyph}
                      {item.label}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>

          <p className="px-3 pb-1.5 pt-5 text-[0.75rem] font-medium uppercase tracking-[0.14em] text-[var(--text-muted)]">
            Chats
          </p>
          {conversations.length === 0 ? (
            <p className="px-3 text-[0.8125rem] leading-6 text-[var(--text-muted)]">
              {hydrated ? "Your chats will appear here." : ""}
            </p>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((item) => (
                <li key={item.id} className="group flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveId(item.id);
                      setDraftChat(null);
                      go("chat");
                    }}
                    className={cn(
                      "flex-1 truncate rounded-lg px-3 py-2 text-left text-[0.875rem] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40",
                      item.id === active?.id
                        ? "bg-[var(--panel-raised)] text-[var(--text-primary)]"
                        : "text-[var(--text-secondary)]",
                    )}
                  >
                    {item.title}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      deleteConversation(item.id);
                      if (activeId === item.id) startNew();
                    }}
                    aria-label={`Delete ${item.title}`}
                    className="rounded-lg p-2 text-[var(--text-muted)] opacity-50 transition-opacity focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
                  >
                    <Trash aria-hidden="true" className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="border-t border-[var(--panel-line)] px-4 py-3.5">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel-raised)] text-[var(--text-secondary)]">
              <UserCircle aria-hidden="true" className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-[0.875rem] text-[var(--text-primary)]">Owner</p>
              <p className="truncate text-[0.75rem] text-[var(--text-muted)]">
                {offline ? "Brain offline" : (status.provider ?? "Core Brain")}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {sidebarOpen ? (
        <button
          type="button"
          aria-label="Close menu"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-[var(--scrim)] lg:hidden"
        />
      ) : null}

      <AppMenu
        key={menuOpen ? "open" : "closed"}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />

      {/* ------------------------------- Main ------------------------------- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-[var(--panel-line)] px-3 py-3">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-2 text-[var(--text-secondary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              <path
                d="M2 4h14M2 9h14M2 14h14"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <CerebroMark className="h-5 w-5 text-[var(--accent)]" />
          <span className="text-[0.875rem] text-[var(--text-secondary)]">
            {VIEWS.find((item) => item.id === view)?.label}
          </span>
          <span className="ml-auto">
            <ThemeToggle />
          </span>
        </header>

        <div ref={threadRef} className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-5 py-8">
            {view === "chat" ? (
              messages.length === 0 ? (
                <BrainIdleView
                  starters={[
                    {
                      text: "What do you know about my projects?",
                      icon: Sparkle,
                    },
                    {
                      text: "Who are the people in my work life?",
                      icon: UserCircle,
                    },
                    {
                      text: "Summarise what is waiting for me",
                      icon: Star,
                    },
                  ]}
                  onStart={(text) => void send(text)}
                  online={!offline}
                />
              ) : (
                <div className="space-y-8 pb-4">
                  {messages.map((message) => (
                    <Message key={message.id} message={message} />
                  ))}
                  {pending ? <Thinking /> : null}
                </div>
              )
            ) : (
              <SectionView view={view} status={status} />
            )}
          </div>
        </div>

        {view === "chat" ? (
          <Composer
            draft={draft}
            onDraft={setDraft}
            onSubmit={() => void send(draft)}
            disabled={offline}
            pending={pending}
            error={error}
          />
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------ Composer ------------------------------ */

function Composer({
  draft,
  onDraft,
  onSubmit,
  disabled,
  pending,
  error,
}: {
  draft: string;
  onDraft: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  pending: boolean;
  error: string | null;
}) {
  return (
    <div className="px-5 pb-5 pt-2">
      <div className="mx-auto w-full max-w-3xl">
        {error ? (
          <p className="mb-3 rounded-lg border border-[var(--danger)]/25 bg-[var(--danger)]/5 px-4 py-3 text-[0.875rem] text-[var(--danger)]">
            {error}
          </p>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="halo-composer flex items-end gap-2 rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] px-2.5 py-2.5"
        >
          {/* Placeholder affordances: visual only until the Brain exposes them. */}
          <button
            type="button"
            disabled
            title="Attachments arrive with a connector"
            aria-label="Attach a file"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[var(--text-muted)] opacity-50"
          >
            <Paperclip aria-hidden="true" className="h-4 w-4" />
          </button>

          <textarea
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                onSubmit();
              }
            }}
            rows={1}
            maxLength={8000}
            disabled={disabled || pending}
            placeholder="Message Brain"
            aria-label="Message Brain"
            className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-1 py-2 text-[0.9375rem] leading-6 text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] disabled:opacity-50"
          />

          <button
            type="button"
            disabled
            title="Web search arrives with a search connector"
            aria-label="Search the web"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[var(--text-muted)] opacity-50"
          >
            <MagnifyingGlass aria-hidden="true" className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled
            title="Voice input is not available yet"
            aria-label="Use voice input"
            className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[var(--text-muted)] opacity-50 sm:flex"
          >
            <Microphone aria-hidden="true" className="h-4 w-4" />
          </button>
          <button
            type="submit"
            disabled={disabled || pending || !draft.trim()}
            aria-label="Send"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-[var(--background)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <PaperPlaneTilt aria-hidden="true" className="h-4 w-4" weight="fill" />
          </button>
        </form>

        <p className="mt-2 text-center text-[0.75rem] text-[var(--text-muted)]">
          Enter to send · Shift + Enter for a new line
        </p>
      </div>
    </div>
  );
}

/* ------------------------------- Thread ------------------------------- */

function Thinking() {
  return (
    <div className="flex items-center gap-3 text-[var(--text-secondary)]">
      <Motor aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />
      <span className="text-[0.9375rem]">Thinking…</span>
      <SpinnerGap aria-hidden="true" className="h-4 w-4 animate-spin" />
    </div>
  );
}

function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] px-4 py-3 text-[0.9375rem] leading-7 text-[var(--text-primary)]">
          <p className="whitespace-pre-wrap">{message.text}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] text-[var(--accent)]">
        <Motor aria-hidden="true" className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        <p
          className={cn(
            "whitespace-pre-wrap text-[0.9375rem] leading-8",
            message.failed ? "text-[var(--danger)]" : "text-[var(--text-primary)]",
          )}
        >
          {message.text}
        </p>
        {message.meta ? <Meta meta={message.meta} /> : null}
      </div>
    </div>
  );
}

/*
 * Answer annotations.
 *
 * Provider, confidence and fallback are internal telemetry: the Brain reports
 * them for observability, not for the person reading the answer. They are
 * dropped on purpose. Only the fact that something was missing stays, because
 * that changes how the answer should be trusted.
 */
function Meta({ meta }: { meta: NonNullable<ChatMessage["meta"]> }) {
  if (meta.missing.length === 0) return null;

  return (
    <p className="border-t border-[var(--panel-line)] pt-3 text-[0.8125rem] leading-6 text-[var(--text-muted)]">
      Not in memory: {meta.missing.join(", ")}
    </p>
  );
}

/* ------------------------------ Sections ------------------------------ */

function SectionView({ view, status }: { view: View; status: BrainStatusDto }) {
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [result, setResult] = useState<CallResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(method: string, input: Record<string, unknown>) {
    setBusy(true);
    try {
      setResult(
        await apiRequest<CallResult>("/api/brain/call", {
          method: "POST",
          body: { method, input },
        }),
      );
    } catch {
      setResult({ ok: false, data: null, error: "Request failed.", code: null });
    } finally {
      setBusy(false);
    }
  }

  const offline = !status.reachable;

  if (view === "search") {
    return (
      <Panel
        title="Search memory"
        hint="Ranked retrieval across everything the Brain has stored"
        onSubmit={() => void run("search", { text: query.trim(), limit: 10 })}
        placeholder="deadline, ayxan, deploy"
        action="Search"
        value={query}
        onChange={setQuery}
        busy={busy}
        disabled={offline}
        result={result}
      />
    );
  }

  if (view === "people") {
    return (
      <Panel
        title="People"
        hint="Identity is resolved deterministically. Ambiguous names are never merged"
        onSubmit={() => void run("resolve_person", { name: name.trim() })}
        placeholder="Ayxan"
        action="Resolve"
        value={name}
        onChange={setName}
        busy={busy}
        disabled={offline}
        result={result}
      />
    );
  }

  if (view === "learning") {
    return (
      <Panel
        title="Learning"
        hint="Counted signals and preferences the Brain has derived"
        onSubmit={() => void run("learning_status", {})}
        placeholder=""
        action="Read"
        value=""
        onChange={() => {}}
        busy={busy}
        disabled={offline}
        result={result}
        hideInput
      />
    );
  }

  if (view === "developer") {
    return (
      <Panel
        title="Developer"
        hint="The Brain reasons over code. Product never analyses it locally"
        onSubmit={() =>
          void run("analyze_developer", {
            repository: "digital-brain-product",
            filePath: "src/example.ts",
            content:
              "export function ratio(a: number, b: number) {\n  return a / b;\n}\n",
            language: "typescript",
          })
        }
        placeholder=""
        action="Analyse"
        value=""
        onChange={() => {}}
        busy={busy}
        disabled={offline}
        result={result}
        hideInput
      />
    );
  }

  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-[1.25rem] font-semibold text-[var(--text-primary)]">
          Capabilities
        </h2>
        <p className="mt-2 text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
          {status.methodCount || status.capabilities.length} methods on the Core
          Brain API
        </p>
        <dl className="mt-6 grid gap-x-10 gap-y-6 sm:grid-cols-2">
          {status.capabilities.map((capability) => (
            <div key={capability.method}>
              <dt className="font-mono text-[0.875rem] font-medium text-[var(--accent)]">
                {capability.method}
              </dt>
              <dd className="mt-1.5 text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
                {capability.summary}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h2 className="text-[1.25rem] font-semibold text-[var(--text-primary)]">
          Event types
        </h2>
        <p className="mt-2 text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
          Only these map a source event into memory
        </p>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[var(--panel-line)]">
                {["Event type", "Source", "Memory", "Required"].map((head) => (
                  <th
                    key={head}
                    className="px-4 py-3 text-[0.8125rem] font-medium text-[var(--text-secondary)]"
                  >
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--panel-line)]">
              {SUPPORTED_SOURCE_EVENTS.map((rule) => (
                <tr key={rule.type}>
                  <td className="px-4 py-4">
                    <code className="font-mono text-[0.875rem] text-[var(--accent)]">
                      {rule.type}
                    </code>
                  </td>
                  <td className="px-4 py-4 text-[0.9375rem] text-[var(--text-secondary)]">
                    {rule.provider}
                  </td>
                  <td className="px-4 py-4 text-[0.9375rem] text-[var(--text-secondary)]">
                    {rule.memoryType}
                  </td>
                  <td className="px-4 py-4">
                    <code className="font-mono text-[0.875rem] text-[var(--text-secondary)]">
                      {rule.required}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Panel({
  title,
  hint,
  onSubmit,
  placeholder,
  action,
  value,
  onChange,
  busy,
  disabled,
  result,
  hideInput,
}: {
  title: string;
  hint: string;
  onSubmit: () => void;
  placeholder: string;
  action: string;
  value: string;
  onChange: (value: string) => void;
  busy: boolean;
  disabled: boolean;
  result: CallResult | null;
  hideInput?: boolean;
}) {
  return (
    <section>
      <h2 className="text-[1.25rem] font-semibold text-[var(--text-primary)]">
        {title}
      </h2>
      <p className="mt-2 text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
        {hint}
      </p>

      {hideInput ? (
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled || busy}
          className={cn(secondaryButtonClassName, "mt-6")}
        >
          {busy ? (
            <SpinnerGap aria-hidden="true" className="h-4 w-4 animate-spin" />
          ) : null}
          {action}
        </button>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="mt-6 flex gap-3"
        >
          <input
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={placeholder}
            maxLength={2000}
            disabled={disabled || busy}
            aria-label={title}
            className={inputClassName}
          />
          <button
            type="submit"
            disabled={disabled || busy || !value.trim()}
            className={cn(secondaryButtonClassName, "shrink-0")}
          >
            {busy ? (
              <SpinnerGap aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : null}
            {action}
          </button>
        </form>
      )}

      {result ? <ResultView result={result} /> : null}
    </section>
  );
}

function ResultView({ result }: { result: CallResult }) {
  if (!result.ok) {
    return (
      <p className="mt-6 rounded-lg border border-[var(--danger)]/25 bg-[var(--danger)]/5 px-4 py-3 text-[0.9375rem] text-[var(--danger)]">
        {result.error}
      </p>
    );
  }

  const data = result.data as Record<string, unknown> | null;
  const items = Array.isArray(data?.items)
    ? data.items
    : Array.isArray(data)
      ? data
      : null;

  if (items) {
    if (items.length === 0) {
      return (
        <p className="mt-6 text-[0.9375rem] text-[var(--text-muted)]">No records.</p>
      );
    }
    return (
      <ul className="mt-6 space-y-3">
        {items.map((item, index) => {
          const record = item as Record<string, unknown>;
          return (
            <li
              key={String(record.memory_id ?? record.person_id ?? index)}
              className="rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] px-4 py-4"
            >
              <div className="flex flex-wrap items-center gap-2 text-[0.75rem] text-[var(--text-muted)]">
                <span>{String(record.type ?? "record")}</span>
                {typeof record.score === "number" ? (
                  <span>score {record.score.toFixed(3)}</span>
                ) : null}
                {typeof record.person_id === "string" ? (
                  <span className="font-mono text-[var(--accent)]">
                    {record.person_id}
                  </span>
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
    <pre className="mt-6 overflow-x-auto rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] p-4 font-mono text-[0.8125rem] leading-6 text-[var(--text-primary)]">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
