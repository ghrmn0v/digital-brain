import type { ConnectomeEdgeKind, ConnectomeNodeKind } from "@/modules/connectome";

/**
 * The Connectome's visual language, kept in one place so the canvas, the
 * inspector and the timeline agree about what a "source" or a "thread" looks
 * like. The palette stays inside the app's existing near-black/slate/cyan range:
 * node kind is carried by shape, ring weight and label, not by hue, so the
 * graph reads as one system instead of a category chart.
 */

export interface NodeStyle {
  label: string;
  /** Short form for the inspector chip. */
  short: string;
  fill: string;
  stroke: string;
  /** Ring drawn around a selected or hovered node. */
  halo: string;
  text: string;
  muted: string;
  description: string;
}

export const nodeStyles: Record<ConnectomeNodeKind, NodeStyle> = {
  source: {
    label: "Source",
    short: "SRC",
    fill: "#0b1220",
    stroke: "#38bdf8",
    halo: "rgba(56, 189, 248, 0.28)",
    text: "#e2e8f0",
    muted: "#64748b",
    description: "A system that sent an event into Product.",
  },
  event: {
    label: "Event",
    short: "EVT",
    fill: "#0f172a",
    stroke: "#94a3b8",
    halo: "rgba(226, 232, 240, 0.22)",
    text: "#f8fafc",
    muted: "#94a3b8",
    description: "Something that actually happened, as recorded.",
  },
  thread: {
    label: "Thread",
    short: "THR",
    fill: "#0c1a24",
    stroke: "#22d3ee",
    halo: "rgba(34, 211, 238, 0.3)",
    text: "#cffafe",
    muted: "#67e8f9",
    description: "Events that share one correlation id.",
  },
  consumer: {
    label: "Consumer",
    short: "CON",
    fill: "#111827",
    stroke: "#64748b",
    halo: "rgba(148, 163, 184, 0.2)",
    text: "#cbd5e1",
    muted: "#64748b",
    description: "A downstream system the event was delivered to.",
  },
  proposal: {
    label: "Proposal",
    short: "PRP",
    fill: "#141a2b",
    stroke: "#a5b4fc",
    halo: "rgba(165, 180, 252, 0.26)",
    text: "#e0e7ff",
    muted: "#a5b4fc",
    description: "Something the Brain proposed for a decision.",
  },
};

export const edgeStyles: Record<ConnectomeEdgeKind, { stroke: string; width: number; dash?: string }> = {
  emitted: { stroke: "rgba(148, 163, 184, 0.34)", width: 1 },
  threaded: { stroke: "rgba(34, 211, 238, 0.4)", width: 1.25 },
  delivered: { stroke: "rgba(56, 189, 248, 0.3)", width: 1 },
  proposed: { stroke: "rgba(165, 180, 252, 0.34)", width: 1.25, dash: "3 3" },
};

export const edgeLabels: Record<ConnectomeEdgeKind, string> = {
  emitted: "emitted",
  threaded: "in thread with",
  delivered: "delivered to",
  proposed: "proposed",
};

/** Shared surface tokens for the graph region, timeline and inspector. */
export const surface = {
  canvas: "#04070f",
  grid: "rgba(148, 163, 184, 0.05)",
  axis: "rgba(148, 163, 184, 0.16)",
  panel: "rgba(9, 14, 26, 0.72)",
  hairline: "rgba(148, 163, 184, 0.14)",
  accent: "#22d3ee",
  accentSoft: "rgba(34, 211, 238, 0.16)",
} as const;
