"use client";

import { cn } from "@/components/ui";

export function Switch({
  checked,
  onCheckedChange,
  disabled = false,
  label,
  className,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn( "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:opacity-50", checked ? "border-sky-300/30 bg-sky-300" : "border-slate-700 bg-[var(--panel-raised)]", className, )}
    >
      <span
        aria-hidden="true"
        className={cn( "h-4 w-4 rounded-full transition-transform", checked ? "translate-x-[1.4rem] bg-[#1a1a1a]" : "translate-x-[0.2rem] bg-slate-400", )}
      />
    </button>
  );
}
