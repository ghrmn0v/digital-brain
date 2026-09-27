"use client";

import {
  Code2,
  Folder,
  Lightning,
  Motor,
  Star,
  UserCircle,
  Waveform,
} from "@/components/icons";

const JUMPS = [
  { href: "/dashboard", label: "Overview", icon: Lightning },
  { href: "/calendar", label: "Calendar", icon: Folder },
  { href: "/tasks", label: "Tasks", icon: Star },
  { href: "/people", label: "People", icon: UserCircle },
  { href: "/memory", label: "Memory", icon: Waveform },
  { href: "/developer", label: "Developer", icon: Code2 },
];

/**
 * The empty conversation. Deliberately short: a hero, three prompts, and a way
 * into the rest of the product. No status noise.
 */
export function BrainIdleView({
  starters,
  onStart,
  online,
}: {
  starters: { text: string; icon: typeof Motor }[];
  onStart: (text: string) => void;
  online: boolean;
}) {
  return (
    <div className="space-y-12 pb-10">
      <div className="flex flex-col items-center gap-5 pt-10 text-center">
        <span className="halo flex h-12 w-12 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] text-[var(--accent)]">
          <Motor aria-hidden="true" className="h-6 w-6" />
        </span>
        <h1 className="text-[1.75rem] font-semibold tracking-tight text-[var(--text-primary)]">
          How can I help?
        </h1>
        <p className="max-w-md text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
          Answers come from what Core Brain has stored. Anything it does not
          know is reported as missing.
        </p>
      </div>

      {!online ? (
        <p className="mx-auto max-w-md rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] px-4 py-3 text-center text-[0.875rem] leading-6 text-[var(--text-secondary)]">
          Core Brain is offline, so questions cannot be answered yet. Start it on
          port 8765.
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        {starters.map((starter) => {
          const Icon = starter.icon;
          return (
            <button
              key={starter.text}
              type="button"
              disabled={!online}
              onClick={() => onStart(starter.text)}
              className="flex items-start gap-3 rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40 disabled:opacity-50"
            >
              <Icon
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0 text-[var(--accent)]"
              />
              <span className="text-[0.875rem] leading-6 text-[var(--text-secondary)]">
                {starter.text}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
        {JUMPS.map((item) => {
          const Icon = item.icon;
          return (
            <a
              key={item.href}
              href={item.href}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--panel-line)] px-3 py-2 text-[0.8125rem] text-[var(--text-secondary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40"
            >
              <Icon aria-hidden="true" className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              {item.label}
            </a>
          );
        })}
      </div>
    </div>
  );
}
