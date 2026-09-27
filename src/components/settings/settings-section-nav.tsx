"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * Which settings section is on screen.
 *
 * Held in a module-level store rather than component state, because
 * IntersectionObserver is a side effect and the React Compiler forbids
 * calling one, or setting state, from the middle of render. The observer
 * publishes here and `useSyncExternalStore` subscribes, so the active
 * section is read like any other external value.
 */

const SECTIONS = [
  "general",
  "permissions",
  "approvals",
  "automations",
  "connectors",
] as const;

export type SettingsSection = (typeof SECTIONS)[number];

let active: SettingsSection = "general";
const listeners = new Set<() => void>();
let observer: IntersectionObserver | null = null;

function publish(next: SettingsSection) {
  if (next === active) return;
  active = next;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1) adoptHashFromUrl();

  if (!observer) {
    observer = new IntersectionObserver(
      (entries) => {
        /*
         * The section the reader is looking at is the last one to start
         * inside the band, not the first. When a new heading scrolls up into
         * view the previous section is still intersecting, with a negative
         * top, so taking the topmost entry would keep reporting the section
         * already scrolled past.
         *
         * Entries also arrive out of order on a fast scroll, so the whole
         * set is reduced rather than trusting the last callback argument.
         */
        const visible = entries.filter((entry) => entry.isIntersecting);
        let current: IntersectionObserverEntry | undefined;
        for (const entry of visible) {
          if (
            !current ||
            entry.boundingClientRect.top > current.boundingClientRect.top
          ) {
            current = entry;
          }
        }
        if (!current) return;
        publish(current.target.id as SettingsSection);
      },
      // A band just below the nav: the section the reader is looking at,
      // not the one that merely touched the viewport.
      { rootMargin: "-52px 0px -70% 0px", threshold: 0 },
    );
  }

  for (const section of SECTIONS) {
    const node = document.getElementById(section);
    if (node) observer.observe(node);
  }

  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): SettingsSection {
  return active;
}

function getServerSnapshot(): SettingsSection {
  return "general";
}

/*
 * A section named in the URL wins over the observer.
 *
 * Arriving on /settings#approvals, the browser scrolls to the fragment
 * before React hydrates. The observer's first callback would otherwise
 * report whatever happened to be under the band at that moment, so the
 * hash is adopted once when the first subscriber attaches and the nav
 * agrees with the scroll the browser already performed.
 */
function adoptHashFromUrl() {
  const hash = window.location.hash.replace("#", "");
  if (SECTIONS.includes(hash as SettingsSection)) {
    publish(hash as SettingsSection);
  }
}

export function useActiveSection(): SettingsSection {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function useSectionJump() {
  return useCallback((section: SettingsSection) => {
    publish(section);
    // replaceState, not an assignment: a section is a view of one page, not
    // a new page, so it should not stack up in the back history. It does go
    // in the URL though, which is what makes a section shareable and lets a
    // legacy /approvals-style redirect land on the right part of the page.
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}#${section}`,
    );
    document
      .getElementById(section)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);
}

const LABELS: Record<SettingsSection, string> = {
  general: "General",
  permissions: "Permissions",
  approvals: "Approvals",
  automations: "Automations",
  connectors: "Connectors",
};

export function SettingsSectionNav() {
  const activeSection = useActiveSection();
  const jump = useSectionJump();

  return (
    <nav
      aria-label="Settings sections"
      className="sticky top-0 z-20 -mx-4 border-b border-[var(--panel-line)] bg-[var(--background)]/90 px-4 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 xl:-mx-10 xl:px-10"
    >
      <ul className="scrollbar-none -mb-px flex items-center gap-1 overflow-x-auto">
        {SECTIONS.map((section) => {
          const current = section === activeSection;
          return (
            <li key={section} className="shrink-0">
              <a
                href={`#${section}`}
                aria-current={current ? "true" : undefined}
                onClick={(event) => {
                  // Let the anchor do the work when JS is off; take over
                  // when it is on so the scroll is smooth and the active
                  // section updates without a layout jump.
                  event.preventDefault();
                  jump(section);
                }}
                className={
                  current
                    ? // The 2px underline sits on the container's border, so
                      // the active tab marks itself without moving anything.
                      "-mb-px inline-flex min-h-12 items-center gap-2 border-b-2 border-[var(--accent)] px-3 text-[0.8125rem] font-semibold text-[var(--text-primary)]"
                    : "-mb-px inline-flex min-h-12 items-center gap-2 border-b-2 border-transparent px-3 text-[0.8125rem] font-medium text-[var(--text-secondary)]"
                }
              >
                {LABELS[section]}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
