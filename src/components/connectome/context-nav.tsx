"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BrainCircuit,
  BriefcaseBusiness,
  CalendarDays,
  CheckCheck,
  Code2,
  Cpu,
  History,
  ListTodo,
  MessageSquareText,
  Network,
  PlugZap,
  RadioTower,
  ShieldCheck,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/components/ui";

/**
 * Context navigation for the Connectome.
 *
 * The Sources section is built from the distinct source values the database
 * actually contains, so it lists WhatsApp or LinkedIn only once something has
 * genuinely arrived from them. A source filter with nothing behind it is a
 * promise the app cannot keep.
 */

export interface SourceFilterItem {
  value: string;
  count: number;
}

export interface ContextNavProps {
  sources: SourceFilterItem[];
  activeSource: string | null;
  onSourceChange: (source: string | null) => void;
  developerModeEnabled: boolean;
  onNavigate?: () => void;
}

const contextItems: Array<{ href: string; label: string; icon: LucideIcon }> = [
  { href: "/connectome", label: "Connectome", icon: Network },
  { href: "/dashboard", label: "Overview", icon: Cpu },
  { href: "/chat", label: "Chat", icon: MessageSquareText },
  { href: "/timeline", label: "Timeline", icon: History },
];

const intelligenceItems: Array<{
  href: string;
  label: string;
  icon: LucideIcon;
  developerModeOnly?: boolean;
  desktopOnly?: boolean;
}> = [
  { href: "/memory", label: "Memories", icon: BrainCircuit },
  { href: "/people", label: "People", icon: Users },
  { href: "/tasks", label: "Tasks", icon: ListTodo },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/approvals", label: "Proposals", icon: CheckCheck },
  {
    href: "/developer",
    label: "Developer",
    icon: Code2,
    developerModeOnly: true,
    desktopOnly: true,
  },
];

const controlItems: Array<{ href: string; label: string; icon: LucideIcon }> = [
  { href: "/automations", label: "Automations", icon: Zap },
  { href: "/permissions", label: "Permissions", icon: ShieldCheck },
  { href: "/connectors", label: "Connectors", icon: PlugZap },
];

const sourceIcons: Record<string, LucideIcon> = {
  whatsapp: RadioTower,
  calendar: CalendarDays,
  linkedin: BriefcaseBusiness,
  core_brain: BrainCircuit,
  todo: ListTodo,
  fly: Zap,
  developer: Code2,
};

function sourceLabel(value: string): string {
  return value
    .split(/[._\-\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function sourceIcon(value: string): LucideIcon {
  return sourceIcons[value.toLowerCase()] ?? RadioTower;
}

function isActive(pathname: string, href: string): boolean {
  return href === "/connectome" ? pathname === href : pathname.startsWith(href);
}

function NavList({
  items,
  developerModeEnabled,
  onNavigate,
}: {
  items: Array<{
    href: string;
    label: string;
    icon: LucideIcon;
    developerModeOnly?: boolean;
    desktopOnly?: boolean;
  }>;
  developerModeEnabled: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <ul className="space-y-0.5">
      {items.map((item) => {
        if (item.developerModeOnly && !developerModeEnabled) return null;
        const active = isActive(pathname, item.href);
        const Icon = item.icon;
        return (
          <li key={item.href} className={item.desktopOnly ? "hidden min-[900px]:block" : undefined}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex min-h-9 items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40",
                active
                  ? "bg-cyan-300/[0.09] text-cyan-100"
                  : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-100",
              )}
            >
              {active ? (
                <span
                  aria-hidden="true"
                  className="absolute inset-y-1.5 left-0 w-px rounded-full bg-cyan-300"
                />
              ) : null}
              <Icon
                aria-hidden="true"
                className={cn(
                  "h-3.5 w-3.5 shrink-0",
                  active ? "text-cyan-300" : "text-zinc-600 group-hover:text-zinc-400",
                )}
              />
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-600">
        {title}
      </p>
      {children}
    </div>
  );
}

export function ContextNav({
  sources,
  activeSource,
  onSourceChange,
  developerModeEnabled,
  onNavigate,
}: ContextNavProps) {
  return (
    <nav aria-label="Context navigation" className="flex-1 overflow-y-auto px-2 py-4">
      <div className="space-y-5">
        <Section title="Context">
          <NavList
            items={contextItems}
            developerModeEnabled={developerModeEnabled}
            onNavigate={onNavigate}
          />
        </Section>

        <Section title="Intelligence">
          <NavList
            items={intelligenceItems}
            developerModeEnabled={developerModeEnabled}
            onNavigate={onNavigate}
          />
        </Section>

        <Section title="Control">
          <NavList
            items={controlItems}
            developerModeEnabled={developerModeEnabled}
            onNavigate={onNavigate}
          />
        </Section>

        <Section title="Sources">
          <button
            type="button"
            onClick={() => onSourceChange(null)}
            aria-pressed={activeSource === null}
            className={cn(
              "flex min-h-9 w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40",
              activeSource === null
                ? "bg-cyan-300/[0.09] text-cyan-100"
                : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-100",
            )}
          >
            <Network
              aria-hidden="true"
              className={cn(
                "h-3.5 w-3.5 shrink-0",
                activeSource === null ? "text-cyan-300" : "text-zinc-600",
              )}
            />
            <span className="min-w-0 flex-1 truncate">All sources</span>
            <span className="shrink-0 text-[11px] tabular-nums text-zinc-600">
              {sources.reduce((total, source) => total + source.count, 0)}
            </span>
          </button>

          {sources.length === 0 ? (
            <p className="px-2.5 py-2 text-[11px] leading-5 text-zinc-600">
              No source has sent an event yet.
            </p>
          ) : (
            <ul className="mt-0.5 space-y-0.5">
              {sources.map((source) => {
                const active = activeSource === source.value;
                const Icon = sourceIcon(source.value);
                return (
                  <li key={source.value}>
                    <button
                      type="button"
                      onClick={() => onSourceChange(active ? null : source.value)}
                      aria-pressed={active}
                      className={cn(
                        "flex min-h-9 w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40",
                        active
                          ? "bg-cyan-300/[0.09] text-cyan-100"
                          : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-100",
                      )}
                    >
                      <Icon
                        aria-hidden="true"
                        className={cn(
                          "h-3.5 w-3.5 shrink-0",
                          active ? "text-cyan-300" : "text-zinc-600",
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate">
                        {sourceLabel(source.value)}
                      </span>
                      <span className="shrink-0 text-[11px] tabular-nums text-zinc-600">
                        {source.count}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Section>
      </div>
    </nav>
  );
}
