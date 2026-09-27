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

/** Flips `data-theme` on <html>, which swaps every colour token at once. */
export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme>(
    subscribeTheme,
    getTheme,
    getServerTheme,
  );

  function toggle() {
    setTheme(theme === "light" ? "dark" : "light");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "light" ? "Use dark theme" : "Use light theme"}
      title={theme === "light" ? "Dark" : "Light"}
      className="rounded-lg p-2 text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
    >
      {theme === "light" ? (
        <Moon aria-hidden="true" className="h-4 w-4" />
      ) : (
        <Sun aria-hidden="true" className="h-4 w-4" />
      )}
    </button>
  );
}
