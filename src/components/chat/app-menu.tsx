"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { MagnifyingGlass, X } from "@/components/icons";
import { cn } from "@/components/ui";

interface Destination {
  href: string;
  label: string;
  hint: string;
}

/** One menu reaches every part of the product. */
const GROUPS: { title: string; items: Destination[] }[] = [
  {
    title: "Overview",
    items: [
      { href: "/dashboard", label: "Overview", hint: "Today at a glance" },
      { href: "/calendar", label: "Calendar", hint: "Events and schedule" },
      { href: "/tasks", label: "Tasks", hint: "What needs doing" },
      { href: "/jobs", label: "Jobs", hint: "Roles and applications" },
      { href: "/settings#approvals", label: "Approvals", hint: "Actions waiting on you" },
    ],
  },
  {
    title: "Knowledge",
    items: [
      { href: "/chat", label: "Chat", hint: "Talk to Core Brain" },
      { href: "/brain", label: "Brain", hint: "Capabilities and events" },
      { href: "/memory", label: "Memory", hint: "What is retained" },
      { href: "/people", label: "People", hint: "Relationships" },
      { href: "/timeline", label: "Timeline", hint: "History" },
      {
        href: "/developer-information",
        label: "Developer updates",
        hint: "Findings from the Brain",
      },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/settings#connectors", label: "Connectors", hint: "LinkedIn and feeds" },
      { href: "/settings#automations", label: "Automations", hint: "Event-driven rules" },
      { href: "/settings#permissions", label: "Permissions", hint: "What Product may do" },
      { href: "/settings", label: "Settings", hint: "Preferences and readiness" },
    ],
  },
];

export function AppMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return GROUPS;
    return GROUPS.map((group) => ({
      ...group,
      items: group.items.filter(
        (item) =>
          item.label.toLowerCase().includes(needle) ||
          item.hint.toLowerCase().includes(needle),
      ),
    })).filter((group) => group.items.length > 0);
  }, [query]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Go to"
      className="fixed inset-0 z-50 flex items-start justify-center bg-[var(--scrim)] px-4 pt-[12vh]"
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        className="flex max-h-[70vh] w-full max-w-xl flex-col overflow-hidden rounded-lg border border-[var(--panel-line)] bg-[var(--panel)]"
      >
        <div className="flex items-center gap-3 border-b border-[var(--panel-line)] px-4">
          <MagnifyingGlass
            aria-hidden="true"
            className="h-4 w-4 text-[var(--text-muted)]"
          />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search and jump to…"
            aria-label="Search destinations"
            className="flex-1 bg-transparent py-4 text-[0.9375rem] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1.5 text-[var(--text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-[0.9375rem] text-[var(--text-muted)]">
              Nothing matches “{query}”.
            </p>
          ) : (
            filtered.map((group) => (
              <div key={group.title} className="mb-1">
                <p className="px-3 pb-1 pt-3 text-[0.75rem] text-[var(--text-muted)]">
                  {group.title}
                </p>
                {group.items.map((item) => (
                  <button
                    key={item.href}
                    type="button"
                    onClick={() => {
                      router.push(item.href);
                      onClose();
                    }}
                    className={cn(
                      "flex w-full items-baseline gap-3 rounded-lg px-3 py-2.5 text-left",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40",
                    )}
                  >
                    <span className="text-[0.9375rem] text-[var(--text-primary)]">
                      {item.label}
                    </span>
                    <span className="text-[0.8125rem] text-[var(--text-muted)]">
                      {item.hint}
                    </span>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
