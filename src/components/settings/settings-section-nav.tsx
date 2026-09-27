"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

/**
 * Which settings section is on screen.
 *
 * The page renders exactly one section, chosen by `?section=`, so this nav is a
 * row of links rather than a control. That is the whole point of the change: it
 * previously scrolled a single long page using an IntersectionObserver acting
 * as a scroll-spy, which meant every section was always mounted, the reader had
 * to scroll to compare two of them, and a section could not be linked to.
 *
 * A link also gets two behaviours for free that a scroll-spy cannot: the
 * browser's back button steps between sections, and a section survives a reload
 * or a shared link.
 */
const SECTIONS = [
  { id: "general", label: "General" },
  { id: "permissions", label: "Permissions" },
  { id: "approvals", label: "Approvals" },
  { id: "automations", label: "Automations" },
  { id: "connectors", label: "Connectors" },
] as const;

export type SettingsSection = (typeof SECTIONS)[number]["id"];

export function SettingsSectionNav() {
  const pathname = usePathname();
  const params = useSearchParams();
  const active = params.get("section") ?? "general";

  return (
    <nav
      aria-label="Settings sections"
      className="flex flex-wrap items-center gap-1 border-b border-[var(--panel-line)] pb-3"
    >
      {SECTIONS.map((section) => {
        const selected = active === section.id;
        return (
          <Link
            key={section.id}
            href={{ pathname, query: { section: section.id } }}
            aria-current={selected ? "page" : undefined}
            className={
              selected
                ? "rounded-lg bg-[var(--panel-raised)] px-3 py-1.5 text-[0.9375rem] font-medium text-[var(--text-primary)]"
                : "rounded-lg px-3 py-1.5 text-[0.9375rem] text-[var(--text-secondary)] transition hover:bg-[var(--panel-raised)] hover:text-[var(--text-primary)]"
            }
          >
            {section.label}
          </Link>
        );
      })}
    </nav>
  );
}
