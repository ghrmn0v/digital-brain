"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Bug,
  BriefcaseBusiness,
  CalendarDays,
  CheckCheck,
  ChevronRight,
  Code2,
  History,
  LayoutDashboard,
  ListTodo,
  Memory,
  Menu,
  MessageCircle,
  Motor,
  PlugZap,
  Settings,
  ShieldCheck,
  Users,
  X,
  Zap,
  type ProductIcon,
} from "@/components/icons";
import { CerebroLogo } from "@/components/brand/cerebro-logo";
import { ThemeToggle } from "@/components/chat/theme-toggle";
import { cn } from "@/components/ui";

type NavigationItem = {
  href: string;
  label: string;
  icon: ProductIcon;
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
      { href: "/chat", label: "Chat", icon: MessageCircle },
      { href: "/brain", label: "Brain", icon: Motor },
      { href: "/memory", label: "Memory", icon: Memory },
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
      className="group flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/60"
      aria-label="Cerebro Flow overview"
    >
      <CerebroLogo />
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
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
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
                      className={cn( "group relative flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50", active ? "bg-[var(--accent)]/[0.11] text-[var(--accent)]" : "text-[var(--text-secondary)] ", )}
                    >
                      {active ? (
                        <span
                          aria-hidden="true"
                          className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-[var(--accent)]"
                        />
                      ) : null}
                      <Icon
                        aria-hidden="true"
                        className={cn("h-4 w-4 shrink-0", active ? "text-[var(--accent)]" : "text-[var(--text-muted)]")}
                      />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {active ? (
                        <ChevronRight
                          aria-hidden="true"
                          className="h-3.5 w-3.5 text-[var(--accent)]/70"
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

export function DashboardShell({
  children,
  developerModeEnabled,
}: {
  children: ReactNode;
  developerModeEnabled: boolean;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);

  // A drawer that only closes by tapping the overlay is unusable from the
  // keyboard. Escape closes it, focus moves in on open and returns to the
  // toggle on close, and the page behind is locked so a touch drag does not
  // scroll the content out from under the panel.
  useEffect(() => {
    if (!mobileOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    const focusFirst = window.requestAnimationFrame(() => {
      const target = drawerRef.current?.querySelector<HTMLElement>(
        "a[href], button:not([disabled])",
      );
      (target ?? drawerRef.current)?.focus();
    });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setMobileOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      window.cancelAnimationFrame(focusFirst);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      (toggleRef.current ?? previouslyFocused)?.focus();
    };
  }, [mobileOpen]);

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--text-primary)]">
      <a
        href="#main-content"
        className="fixed left-3 top-3 z-[100] -translate-y-20 rounded-lg border border-[var(--accent)]/30 bg-[var(--panel)] px-4 py-2 text-sm font-semibold text-[var(--accent)] transition focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/60"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-[var(--panel-line)] bg-[var(--panel)] lg:flex">
        <div className="flex h-20 items-center border-b border-[var(--panel-line)]/80 px-5">
          <Brand />
        </div>
        <Navigation developerModeEnabled={developerModeEnabled} />
      </aside>

      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[var(--panel-line)]/80 bg-[var(--background)]/85 px-4 backdrop-blur-xl lg:hidden">
        <Brand />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            ref={toggleRef}
            type="button"
            aria-label={mobileOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation"
            onClick={() => setMobileOpen((open) => !open)}
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--panel-line)] bg-[var(--panel)] text-[var(--text-primary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/60"
          >
            {mobileOpen ? (
              <X aria-hidden="true" className="h-5 w-5" />
            ) : (
              <Menu aria-hidden="true" className="h-5 w-5" />
            )}
          </button>
        </div>
      </header>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation overlay"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-[var(--scrim)] backdrop-blur-sm"
          />
          <aside
            id="mobile-navigation"
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col border-r border-[var(--panel-line)] bg-[var(--panel)]"
          >
            <div className="flex h-16 items-center justify-between border-b border-[var(--panel-line)] px-4">
              <Brand />
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--text-secondary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/60"
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>
            <Navigation
              developerModeEnabled={developerModeEnabled}
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <div className="hidden h-16 items-center justify-end border-b border-[var(--panel-line)]/70 bg-[var(--background)]/60 px-8 backdrop-blur lg:flex">
          <ThemeToggle />
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
