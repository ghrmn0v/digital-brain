"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, Settings2, X } from "lucide-react";
import type { ConnectomeNodeDto } from "@/modules/connectome";
import { nodeStyles } from "@/components/connectome/theme";

/**
 * The global command bar.
 *
 * It searches the graph the application actually has, and it navigates to the
 * screens that exist. It is explicitly not a memory search: the Core Brain owns
 * that and Product has no read path, so pretending otherwise here would be the
 * single most misleading thing this interface could do. When nothing matches,
 * the result list says so rather than padding itself.
 */

export interface CommandTarget {
  id: string;
  label: string;
  group: string;
  href: string;
  keywords?: string;
}

export function CommandBar({
  nodes,
  targets,
}: {
  nodes: ConnectomeNodeDto[];
  targets: CommandTarget[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      previouslyFocused?.focus?.();
    };
  }, [open]);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const nodeHits: CommandTarget[] = needle
      ? nodes
          .filter(
            (node) =>
              node.label.toLowerCase().includes(needle) ||
              (node.detail ?? "").toLowerCase().includes(needle) ||
              node.kind.includes(needle),
          )
          .slice(0, 6)
          .map((node) => ({
            id: node.id,
            label: node.label,
            group: nodeStyles[node.kind].label,
            href: `/connectome?node=${encodeURIComponent(node.id)}`,
            keywords: node.detail ?? undefined,
          }))
      : [];

    const pageHits: CommandTarget[] = needle
      ? targets
          .filter(
            (target) =>
              target.label.toLowerCase().includes(needle) ||
              target.keywords?.toLowerCase().includes(needle),
          )
          .slice(0, 5)
      : targets.slice(0, 5);

    return [...nodeHits, ...pageHits];
  }, [nodes, query, targets]);

  const go = (target: CommandTarget) => {
    setOpen(false);
    setQuery("");
    router.push(target.href);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-keyshortcuts="Meta+K Control+K"
        className="group mx-auto flex h-9 w-full max-w-xl items-center gap-2.5 rounded-full border border-[var(--panel-line)]/70 bg-[var(--panel)]/60 px-3.5 text-left backdrop-blur transition hover:border-[var(--text-muted)] hover:bg-[var(--panel)]/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
      >
        <Search aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)]" />
        <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-secondary)]">
          Search your brain
        </span>
        <kbd className="hidden shrink-0 rounded border border-[var(--panel-line)]/80 bg-[var(--panel-line)]/80 px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-secondary)] sm:inline-block">
          ⌘K
        </kbd>
      </button>

      {open ? (
        <div className="fixed inset-0 z-[120] flex items-start justify-center px-4 pt-[12vh]">
          <button
            type="button"
            aria-label="Close search"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-[var(--background)]/80 backdrop-blur-sm"
          />
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
              aria-label="Search Cerebro Flow"
            className="relative w-full max-w-xl overflow-hidden rounded-xl border border-[var(--panel-line)]/80 bg-[var(--panel)]/95 shadow-2xl backdrop-blur-xl"
          >
            <div className="flex items-center gap-2.5 border-b border-[var(--panel-line)] px-4">
              <Search aria-hidden="true" className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setCursor(0);
                }}
                onKeyDown={(event) => {
                  if (event.key === "ArrowDown") {
                    event.preventDefault();
                    setCursor((current) => Math.min(current + 1, results.length - 1));
                  } else if (event.key === "ArrowUp") {
                    event.preventDefault();
                    setCursor((current) => Math.max(current - 1, 0));
                  } else if (event.key === "Enter" && results[cursor]) {
                    event.preventDefault();
                    go(results[cursor]);
                  }
                }}
                placeholder="Search your brain"
                aria-label="Search your brain"
                className="h-12 min-w-0 flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
              />
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close search"
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[var(--text-secondary)] transition hover:bg-[var(--panel-line)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                <X aria-hidden="true" className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="max-h-[min(24rem,50vh)] overflow-y-auto p-1.5">
              {results.length === 0 ? (
                <p className="px-3 py-6 text-center text-xs leading-5 text-[var(--text-secondary)]">
                  Nothing in this graph matches “{query}”.
                  <span className="mt-1 block text-[var(--text-muted)]">
                    This searches events recorded on this device, not Brain memories.
                  </span>
                </p>
              ) : (
                <ul role="listbox" aria-label="Search results">
                  {results.map((result, index) => (
                    <li key={`${result.group}-${result.id}`}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={index === cursor}
                        onMouseEnter={() => setCursor(index)}
                        onClick={() => go(result)}
                        className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition focus-visible:outline-none ${
                          index === cursor
                            ? "bg-cyan-300/10 text-cyan-50"
                            : "text-[var(--text-primary)] hover:bg-[var(--panel-line)]/70"
                        }`}
                      >
                        <span className="w-16 shrink-0 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                          {result.group}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm">{result.label}</span>
                          {result.keywords ? (
                            <span className="block truncate text-[11px] text-[var(--text-secondary)]">
                              {result.keywords}
                            </span>
                          ) : null}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="border-t border-[var(--panel-line)] px-4 py-2 text-[11px] text-[var(--text-muted)]">
              Searches events recorded on this device. Brain memories are not
              readable from Product yet.
            </p>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function CommandSettingsLink() {
  return (
    <Link
      href="/settings"
      aria-label="Open settings"
      title="Settings"
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--panel-line)]/70 bg-[var(--panel)]/60 text-[var(--text-secondary)] backdrop-blur transition hover:border-[var(--text-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
    >
      <Settings2 aria-hidden="true" className="h-4 w-4" />
    </Link>
  );
}
