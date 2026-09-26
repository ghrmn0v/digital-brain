"use client";

import { useMemo } from "react";
import { CalendarClock } from "lucide-react";
import type { ConnectomeNodeDto } from "@/modules/connectome";
import { formatDateTime } from "@/lib/client/format";
import { nodeStyles } from "@/components/connectome/theme";

/**
 * The temporal axis of the brain, drawn from the timestamps that are actually
 * stored on the event nodes.
 *
 * When every event lands on the same day — which is exactly what a first demo
 * run looks like — a linear year scale would be an empty ruler with a single
 * tick in the middle. The scale therefore falls back to time-of-day once the
 * real span drops below a day, so the rail shows the shape of what happened
 * instead of pretending the data is sparse. When there is no timestamped event
 * at all it says so rather than inventing a position.
 */

const DAY_MS = 86_400_000;

export interface TimelineRailProps {
  nodes: ConnectomeNodeDto[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  now: Date;
}

interface Placement {
  node: ConnectomeNodeDto;
  at: number;
  time: number;
}

type RailMode = "empty" | "day" | "span";

export function ConnectomeTimeline({
  nodes,
  selectedId,
  onSelect,
  now,
}: TimelineRailProps) {
  const { placements, mode, caption } = useMemo(() => {
    const dated = nodes
      .filter((node): node is ConnectomeNodeDto & { occurredAt: string } =>
        Boolean(node.occurredAt),
      )
      .map((node) => ({ node, time: new Date(node.occurredAt).getTime() }))
      .filter((entry) => Number.isFinite(entry.time))
      .sort((left, right) => left.time - right.time);

    if (dated.length === 0) {
      return {
        placements: [] as Placement[],
        mode: "empty" as const,
        caption: "No timestamped events yet.",
      };
    }

    const first = dated[0].time;
    const last = dated[dated.length - 1].time;
    const span = Math.max(last - first, 0);

    // Sub-day data gets a time-of-day axis; anything wider keeps real dates.
    const withinDay = span < DAY_MS;
    const earliest = withinDay ? first - span * 0.08 - 60_000 : first;
    const latest = withinDay ? last + span * 0.08 + 60_000 : last;
    const width = Math.max(1, latest - earliest);

    return {
      placements: dated.map((entry) => ({
        node: entry.node,
        time: entry.time,
        at: ((entry.time - earliest) / width) * 100,
      })),
      mode: withinDay ? ("day" as const) : ("span" as const),
      caption: withinDay
        ? "Today, by time of day"
        : `${new Date(first).toLocaleDateString("en-US", {
            month: "short",
            year: "numeric",
          })} — ${new Date(last).toLocaleDateString("en-US", {
            month: "short",
            year: "numeric",
          })}`,
    };
  }, [nodes]);

  if (placements.length === 0) {
    return (
      <div className="flex items-center gap-2.5 px-4 py-3 text-xs text-slate-500">
        <CalendarClock aria-hidden="true" className="h-3.5 w-3.5" />
        Your timeline will appear as Digital Brain receives events.
      </div>
    );
  }

  return (
    <div className="px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Timeline
        </p>
        <p className="text-[11px] text-slate-600">
          {placements.length} event{placements.length === 1 ? "" : "s"} · {caption}
        </p>
      </div>

      <div className="relative h-14 select-none">
        <div
          aria-hidden="true"
          className="absolute left-0 right-0 top-6 h-px bg-slate-800"
        />
        <div
          aria-hidden="true"
          className="absolute top-2 h-3.5 w-px bg-slate-700/60"
          style={{ left: 0 }}
        />
        <div
          aria-hidden="true"
          className="absolute right-0 top-2 h-3.5 w-px bg-slate-700/60"
        />
        <span
          aria-hidden="true"
          className="absolute top-4 h-4 w-px bg-cyan-400/40"
          style={{ left: `${nowAt(now, placements, mode)}%` }}
        />

        {placements.map(({ node, at }) => {
          const selected = node.id === selectedId;
          const style = nodeStyles[node.kind];
          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelect(selected ? null : node.id)}
              aria-pressed={selected}
              title={`${formatDateTime(node.occurredAt)} · ${node.label}`}
              className="group absolute top-0 -ml-2 flex h-12 w-4 flex-col items-center justify-end focus-visible:outline-none"
              style={{ left: `${Math.min(98, Math.max(2, at))}%` }}
            >
              <span
                className={`h-2 w-2 rounded-full border transition ${
                  selected
                    ? "scale-125 border-cyan-200 bg-cyan-300"
                    : "border-slate-600 bg-slate-800 group-hover:border-slate-400"
                }`}
                style={selected ? undefined : { borderColor: style.stroke }}
              />
              <span
                className={`mt-1 h-1.5 w-px transition ${
                  selected ? "bg-cyan-300/70" : "bg-slate-800"
                }`}
              />
              <span className="sr-only">
                {formatDateTime(node.occurredAt)}, {node.label}
              </span>
              <span
                aria-hidden="true"
                className="pointer-events-none absolute bottom-full mb-1 hidden whitespace-nowrap rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] text-slate-200 group-hover:block group-focus-visible:block"
              >
                {node.label.length > 30 ? `${node.label.slice(0, 29)}…` : node.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Where "now" sits on the rail, clamped so the marker stays on the surface. */
function nowAt(now: Date, placements: Placement[], mode: RailMode): number {
  const times = placements.map((placement) => placement.time);
  const first = Math.min(...times);
  const last = Math.max(...times);
  const target = now.getTime();

  if (mode === "day") {
    if (target <= first) return 2;
    if (target >= last) return 98;
  }
  const width = Math.max(1, last - first);
  return Math.min(98, Math.max(2, ((target - first) / width) * 100));
}
