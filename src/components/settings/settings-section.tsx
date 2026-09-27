import type { ReactNode } from "react";

/**
 * One settings section.
 *
 * The id is the anchor the section nav and the legacy routes target, so it
 * is part of the URL contract and must not be renamed casually.
 */
export function SettingsSection({
  id,
  title,
  eyebrow,
  description,
  children,
}: {
  id: string;
  title: string;
  eyebrow?: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      // scroll-mt clears the sticky section nav, so a jump from the nav
      // lands on the heading instead of under it.
      className="space-y-4 scroll-mt-16"
    >
      <div>
        {/* The eyebrow sits inline with the title: one line of identity
            rather than a stacked pair, and the nav shares the same row. */}
        <h2
          id={`${id}-heading`}
          className="flex items-baseline gap-3 text-xl font-semibold tracking-tight text-[var(--text-primary)]"
        >
          {title}
          {eyebrow ? (
            <span className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--accent)]">
              {eyebrow}
            </span>
          ) : null}
        </h2>
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
            {description}
          </p>
        ) : null}
      </div>
      {children}
    </section>
  );
}
