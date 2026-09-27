"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "@/components/icons";
import {
  getServerTheme,
  getTheme,
  setTheme,
  subscribeTheme,
  type Theme,
} from "@/lib/theme";

/**
 * Theme switch, pinned to the foot of the sidebar.
 *
 * mt-auto is what holds it there: the sidebar is a flex column, the nav
 * above it takes the space it needs, and the leftover goes to this row. The
 * divider separates it from navigation rather than from settings, so the
 * boundary is "this is not a page".
 *
 * A segmented control rather than a single button, because the two states
 * are worth naming. The whole control reports the current theme as its
 * accessible name, so a screen reader hears "Dark" and not two unlabelled
 * glyphs.
 */
export function SidebarTheme() {
  const theme = useSyncExternalStore<Theme>(
    subscribeTheme,
    getTheme,
    getServerTheme,
  );

  return (
    <div className="mt-auto border-t border-[var(--panel-line)] p-3">
      <div
        role="radiogroup"
        aria-label="Colour theme"
        className="flex items-center gap-1 rounded-lg border border-[var(--panel-line)] bg-[var(--background)] p-1"
      >
        <ThemeOption
          active={theme === "light"}
          label="Light theme"
          onSelect={() => setTheme("light")}
        >
          <Sun aria-hidden="true" className="h-4 w-4" />
          <span className="text-[0.75rem] font-semibold">Light</span>
        </ThemeOption>
        <ThemeOption
          active={theme === "dark"}
          label="Dark theme"
          onSelect={() => setTheme("dark")}
        >
          <Moon aria-hidden="true" className="h-4 w-4" />
          <span className="text-[0.75rem] font-semibold">Dark</span>
        </ThemeOption>
      </div>
    </div>
  );
}

function ThemeOption({
  active,
  label,
  onSelect,
  children,
}: {
  active: boolean;
  label: string;
  onSelect: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      aria-label={label}
      onClick={onSelect}
      className={
        active
          ? "flex min-h-8 flex-1 items-center justify-center gap-1.5 rounded-md bg-[var(--panel-raised)] text-[var(--text-primary)]"
          : "flex min-h-8 flex-1 items-center justify-center gap-1.5 rounded-md text-[var(--text-muted)]"
      }
    >
      {children}
    </button>
  );
}
