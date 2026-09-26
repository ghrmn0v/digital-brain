import Link from "next/link";
import type { ReactNode } from "react";
import type { ProductIcon } from "@/components/icons";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Inbox,
  LoaderCircle,
} from "@/components/icons";

export function cn( ...classes: Array<string | false | null | undefined> ): string {
  return classes.filter(Boolean).join(" ");
}

export const inputClassName =
  "min-h-12 w-full rounded-lg border border-[var(--panel-line)]/70 bg-[var(--panel)]/60 px-4 py-3 text-[0.9375rem] leading-6 text-[var(--text-primary)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-sky-400/70 focus:ring-2 focus:ring-sky-400/20 disabled:cursor-not-allowed disabled:opacity-50";

export const selectClassName = cn(
  inputClassName,
  // Chevron drawn as an inline SVG data URI, so no gradient is involved.
  "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2016%2016%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%221.5%22%3E%3Cpath%20d%3D%22M4%206l4%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:16px_16px] bg-[position:right_0.75rem_center] bg-no-repeat pr-9",
);

export const primaryButtonClassName =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-sky-300/20 bg-sky-300 px-4 py-2 text-sm font-semibold text-slate-950 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-55";

export const secondaryButtonClassName =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-[var(--panel)]/80 px-4 py-2 text-sm font-semibold text-[var(--text-primary)] transition   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-50";

export const dangerButtonClassName =
  "inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-1.5 text-sm font-semibold text-rose-200 transition   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-50";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-5 border-b border-[var(--panel-line)]/80 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-[var(--accent)]">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          {title}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
          {description}
        </p>
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}

export function Panel({
  children,
  className,
  as: Component = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "div";
}) {
  return (
    <Component
      className={cn( "rounded-lg border border-[var(--panel-line)]/90 bg-[var(--panel)]/55 backdrop-blur-sm",
        className,
      )}
    >
      {children}
    </Component>
  );
}

export function SectionHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 border-b border-[var(--panel-line)]/70 px-6 py-6 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
      <div className="min-w-0">
        <h2 className="text-[1.0625rem] font-semibold leading-7 text-[var(--text-primary)]">
          {title}
        </h2>
        {description ? (
          <p className="mt-1.5 max-w-prose text-[0.9375rem] leading-7 text-[var(--text-secondary)]">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

const badgeToneClasses: Record<BadgeTone, string> = {
  neutral: "border-slate-700 bg-[var(--panel-raised)] text-[var(--text-primary)]",
  info: "border-sky-400/20 bg-sky-400/10 text-[var(--accent)]",
  success: "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
  warning: "border-amber-400/20 bg-amber-400/10 text-amber-200",
  danger: "border-rose-400/20 bg-rose-400/10 text-rose-200",
};

const badgeDotClasses: Record<BadgeTone, string> = {
  neutral: "bg-slate-400",
  info: "bg-sky-300",
  success: "bg-emerald-300",
  warning: "bg-amber-300",
  danger: "bg-rose-300",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
}) {
  return (
    <span
      className={cn( "inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide", badgeToneClasses[tone], )}
    >
      {dot ? (
        <span
          aria-hidden="true"
          className={cn("h-1.5 w-1.5 rounded-full", badgeDotClasses[tone])}
        />
      ) : null}
      {children}
    </span>
  );
}

function statusTone(status: string): BadgeTone {
  const normalized = status.toLowerCase();

  if (
    ["completed", "confirmed", "healthy", "done", "saved", "applied", "enabled", "delivered", "active"].includes(
      normalized,
    )
  ) {
    return "success";
  }
  if (
    ["in_progress", "pending", "pending_approval", "tentative", "degraded", "scheduled", "processing", "high"].includes(
      normalized,
    )
  ) {
    return "warning";
  }
  if (
    ["blocked", "error", "failed", "rejected", "off", "disconnected", "overdue", "urgent"].includes(
      normalized,
    )
  ) {
    return "danger";
  }
  if (["automatic", "seen", "received", "medium"].includes(normalized)) return "info";
  return "neutral";
}

export function StatusBadge({ status }: { status: string }) {
  const label = status
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
  return (
    <Badge tone={statusTone(status)} dot>
      {label}
    </Badge>
  );
}

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
}: {
  title: string;
  description: string;
  icon?: ProductIcon;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-12">
      <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-slate-700 bg-[var(--panel-raised)] text-[var(--text-secondary)]">
        <Icon aria-hidden="true" className="h-5 w-5" />
      </div>
      <h3 className="mt-4 text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-1 max-w-sm text-sm leading-6 text-[var(--text-muted)]">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorBanner({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-lg border border-rose-400/25 bg-rose-500/[0.08] px-4 py-3 text-sm text-rose-100 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex min-w-0 items-start gap-3">
        <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-0.5 break-words text-rose-200/80">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded-lg border border-rose-300/20 px-3 py-1.5 text-xs font-semibold text-rose-100 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/50"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function SuccessBanner({ message }: { message: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.08] px-4 py-3 text-sm text-emerald-100"
    >
      <CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <p>{message}</p>
    </div>
  );
}

export function InlineNotice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "warning";
}) {
  const Icon = tone === "warning" ? AlertTriangle : AlertCircle;
  return (
    <div
      className={cn( "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm", tone === "warning" ? "border-amber-400/20 bg-amber-400/[0.07] text-amber-100" : "border-sky-400/20 bg-sky-400/[0.07] text-sky-100", )}
    >
      <Icon aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="leading-6">{children}</div>
    </div>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  href,
}: {
  label: string;
  value: number | string;
  detail: string;
  icon: ProductIcon;
  href: string;
}) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
          {label}
        </p>
        <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--panel-line)]/80 bg-[var(--panel-raised)] text-[var(--text-secondary)]">
          <Icon aria-hidden="true" className="h-4 w-4" />
        </span>
      </div>
      <p className="mt-5 text-3xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">{detail}</p>
    </>
  );

  return (
    <Link
      href={href}
      className="group rounded-lg border border-[var(--panel-line)]/90 bg-[var(--panel)]/55 p-5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50"
    >
      {content}
    </Link>
  );
}

export function ButtonSpinner() {
  return (
    <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-lg bg-[var(--panel-raised)]/80", className)}
    />
  );
}
