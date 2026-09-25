"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  Bot,
  BrainCircuit,
  Bug,
  BriefcaseBusiness,
  CalendarDays,
  CheckCheck,
  ChevronRight,
  CircleDot,
  Clock3,
  Code2,
  History,
  LayoutDashboard,
  ListTodo,
  Menu,
  PlugZap,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/components/ui";

type NavigationItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  developerModeOnly?: boolean;
  desktopOnly?: boolean;
};

type NavigationSection = {
  label: string;
  items: NavigationItem[];
};

const navigation: NavigationSection[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
      { href: "/tasks", label: "Tasks", icon: ListTodo },
      { href: "/calendar", label: "Calendar", icon: CalendarDays },
      { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
    ],
  },
  {
    label: "Control plane",
    items: [
      { href: "/approvals", label: "Approvals", icon: CheckCheck },
      { href: "/automations", label: "Automations", icon: Zap },
      { href: "/permissions", label: "Permissions", icon: ShieldCheck },
      { href: "/connectors", label: "Connectors", icon: PlugZap },
      {
        href: "/developer",
        label: "Developer Mode",
        icon: Code2,
        developerModeOnly: true,
        desktopOnly: true,
      },
    ],
  },
  {
    label: "Knowledge & system",
    items: [
      { href: "/timeline", label: "Timeline", icon: History },
      { href: "/memory", label: "Memory", icon: BrainCircuit },
      { href: "/people", label: "People", icon: Users },
      {
        href: "/developer-information",
        label: "Developer Updates",
        icon: Bug,
      },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/dashboard" ? pathname === href : pathname.startsWith(href);
}

function Brand() {
  return (
    <Link
      href="/dashboard"
      className="group flex items-center gap-3 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
      aria-label="Digital Brain Product dashboard"
    >
      <span className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200 shadow-[0_0_30px_-14px_rgba(34,211,238,0.8)]">
        <Bot aria-hidden="true" className="h-5 w-5" />
        <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full border-2 border-slate-950 bg-emerald-300" />
      </span>
      <span>
        <span className="block text-sm font-semibold tracking-tight text-white">
          Digital Brain
        </span>
        <span className="block text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">
          Product OS
        </span>
      </span>
    </Link>
  );
}

function Navigation({
  developerModeEnabled,
  onNavigate,
}: {
  developerModeEnabled: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary navigation" className="flex-1 overflow-y-auto px-3 py-5">
      <div className="space-y-6">
        {navigation.map((section) => (
          <div key={section.label}>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">
              {section.label}
            </p>
            <ul className="space-y-1">
              {section.items
                .filter(
                  (item) =>
                    !item.developerModeOnly || developerModeEnabled,
                )
                .map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <li
                    key={item.href}
                    className={
                      item.desktopOnly ? "hidden min-[900px]:block" : undefined
                    }
                  >
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group relative flex min-h-10 items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50",
                        active
                          ? "bg-cyan-300/[0.11] text-cyan-100"
                          : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100",
                      )}
                    >
                      {active ? (
                        <span
                          aria-hidden="true"
                          className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-cyan-300"
                        />
                      ) : null}
                      <Icon
                        aria-hidden="true"
                        className={cn(
                          "h-4 w-4 shrink-0",
                          active ? "text-cyan-300" : "text-slate-500 group-hover:text-slate-300",
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {active ? (
                        <ChevronRight
                          aria-hidden="true"
                          className="h-3.5 w-3.5 text-cyan-300/70"
                        />
                      ) : null}
                    </Link>
                  </li>
                );
                })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}

function SidebarFooter() {
  return (
    <div className="border-t border-slate-800/80 p-4">
      <div className="rounded-xl border border-slate-800 bg-slate-950/45 p-3">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
          <CircleDot aria-hidden="true" className="h-3.5 w-3.5 text-emerald-300" />
          Local-first workspace
        </div>
        <p className="mt-1.5 text-[11px] leading-5 text-slate-600">
          Product data stays in the local SQLite database.
        </p>
      </div>
    </div>
  );
}

export function DashboardShell({
  children,
  developerModeEnabled,
}: {
  children: ReactNode;
  developerModeEnabled: boolean;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <a
        href="#main-content"
        className="fixed left-3 top-3 z-[100] -translate-y-20 rounded-lg border border-cyan-300/30 bg-slate-900 px-4 py-2 text-sm font-semibold text-cyan-100 shadow-lg transition focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-slate-800/90 bg-slate-950/95 backdrop-blur-xl lg:flex">
        <div className="flex h-20 items-center border-b border-slate-800/80 px-5">
          <Brand />
        </div>
        <Navigation developerModeEnabled={developerModeEnabled} />
        <SidebarFooter />
      </aside>

      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-800/80 bg-slate-950/85 px-4 backdrop-blur-xl lg:hidden">
        <Brand />
        <button
          type="button"
          aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={mobileOpen}
          aria-controls="mobile-navigation"
          onClick={() => setMobileOpen((open) => !open)}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-300 transition hover:border-slate-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
        >
          {mobileOpen ? (
            <X aria-hidden="true" className="h-5 w-5" />
          ) : (
            <Menu aria-hidden="true" className="h-5 w-5" />
          )}
        </button>
      </header>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation overlay"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-slate-950/75 backdrop-blur-sm"
          />
          <aside
            id="mobile-navigation"
            className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col border-r border-slate-800 bg-slate-950 shadow-2xl"
          >
            <div className="flex h-16 items-center justify-between border-b border-slate-800 px-4">
              <Brand />
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>
            <Navigation
              developerModeEnabled={developerModeEnabled}
              onNavigate={() => setMobileOpen(false)}
            />
            <SidebarFooter />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <div className="hidden h-16 items-center justify-between border-b border-slate-800/70 bg-slate-950/60 px-8 backdrop-blur lg:flex">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
            <Sparkles aria-hidden="true" className="h-3.5 w-3.5 text-cyan-300" />
            Personal product control plane
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />
            Fresh server data on every visit
          </div>
        </div>
        <main
          id="main-content"
          className="mx-auto w-full max-w-[96rem] px-4 py-6 sm:px-6 sm:py-8 lg:px-8 xl:px-10"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
