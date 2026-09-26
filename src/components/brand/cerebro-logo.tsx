/**
 * Cerebro Flow mark.
 *
 * A node graph that reads as a knowledge graph rather than a generic sparkle:
 * one hub, a left fan of three nodes, and a right axis. Drawn inline so it
 * inherits the current theme and needs no image asset.
 */

export function CerebroMark({
  className,
  accent = "currentColor",
}: {
  className?: string;
  accent?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      {/* left fan */}
      <path
        d="M8.5 12H3M12 7.5 7.6 4.2M12 16.5l-4.4 3.3"
        stroke={accent}
        strokeWidth="1.1"
        strokeLinecap="round"
        opacity="0.75"
      />
      {/* right axis */}
      <path
        d="M14.5 12H21"
        stroke={accent}
        strokeWidth="1.1"
        strokeLinecap="round"
        opacity="0.5"
      />
      {/* hub ring */}
      <circle cx="11.5" cy="12" r="3.1" stroke={accent} strokeWidth="1.2" />
      {/* terminals */}
      <circle cx="3" cy="12" r="1.05" fill={accent} opacity="0.7" />
      <circle cx="21" cy="12" r="1.05" fill={accent} opacity="0.45" />
      <circle cx="6.6" cy="3.6" r="0.85" fill={accent} opacity="0.6" />
      <circle cx="6.6" cy="20.4" r="0.85" fill={accent} opacity="0.6" />
    </svg>
  );
}

/** Full lockup: mark plus wordmark. */
export function CerebroLogo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <CerebroMark className="h-6 w-6 text-[var(--accent)]" />
      {compact ? null : (
        <span className="text-[0.9375rem] font-semibold tracking-[0.08em] text-[var(--text-primary)]">
          CEREBRO
          <span className="ml-2 font-normal tracking-[0.24em] text-[var(--text-muted)]">
            FLOW
          </span>
        </span>
      )}
    </span>
  );
}
