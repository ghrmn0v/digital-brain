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
      // scroll-mt clears the sticky top bar and the section nav, so a jump
      // from the nav lands on the heading instead of under it.
      className="scroll-mt-32 space-y-4"
    >
      <div>
        {eyebrow ? (
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-[var(--accent)]">
            {eyebrow}
          </p>
        ) : null}
        <h2
          id={`${id}-heading`}
          className="text-xl font-semibold tracking-tight text-[var(--text-primary)]"
        >
          {title}
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
