/**
 * The design tokens.
 *
 * These existed as literal hex values scattered through the components, which
 * is how two shells ended up looking like two products: the Connectome ground
 * was `#04070f`, the dashboard's was `#020617`, the brand mark's is `#09090B`,
 * and the SVG canvas needed real colour rather than a class. Every one of those
 * was a separate decision made in a different file.
 *
 * A token is the smallest unit of this decision, so it is the smallest place to
 * change it. The palette is deliberately near-monochrome: surfaces step in
 * small luminance increments, borders are one hairline step above their surface,
 * and a single cyan accent carries "intelligence / active / selected" and
 * nothing else. Node-kind in the graph is carried by shape and ring weight, not
 * by hue, which is what keeps the map from turning into a category chart.
 *
 * Tailwind classes use the zinc scale for type and borders, so the token values
 * below exist mainly for the places a class cannot reach: the SVG canvas, the
 * favicon, and anything inline in a style object.
 */

export const palette = {
  /** Base ground. Matches the brand mark so the app and the logo agree. */
  ground: "#09090B",
  /** Slightly raised surface, used for the shell behind panels. */
  surface: "#0B0B0E",
  /** A panel or input sitting on the ground. */
  raised: "#111113",
  /** A hover or selected row. */
  overlay: "#17171A",
  /** Single hairline border. Deliberately quiet. */
  border: "#27272A",
  /** A stronger border, for a control that needs to read as pressable. */
  borderStrong: "#3F3F46",

  text: "#FAFAFA",
  textMuted: "#A1A1AA",
  /**
   * The caption and section-label tier. These are the two dimmest steps in the
   * ramp and both are load-bearing: captions and uppercase labels are the text
   * a reader spends the least time on, so they need to be quieter than body
   * copy without becoming unreadable. Measured against the composited grounds
   * (a `zinc-900/55` panel over `zinc-950`, and the page itself) these land at
   * 6.0:1 and 4.8:1, where Tailwind's own `zinc-500` and `zinc-600` would give
   * 4.0:1 and 2.5:1 and fail WCAG AA at the 10-12px these are used. They are
   * mirrored as `zinc-450` and `zinc-550` in `globals.css`.
   */
  textSubtle: "#8E8E99",
  textFaint: "#7E7E8A",

  /** The only accent. Used for intelligence, selection and focus. */
  accent: "#22D3EE",
  accentMuted: "#67E8F9",
  accentSurface: "rgba(34, 211, 238, 0.10)",

  success: "#4ADE80",
  warning: "#FBBF24",
  danger: "#F87171",
} as const;

/**
 * Graph surface tokens.
 *
 * The canvas is SVG, so these cannot be Tailwind classes. `grid` is the faint
 * dot pattern; `axis` is the timeline rail.
 */
export const surface = {
  canvas: palette.ground,
  grid: "rgba(161, 161, 170, 0.045)",
  axis: "rgba(161, 161, 170, 0.16)",
  panel: "rgba(17, 17, 19, 0.72)",
  hairline: "rgba(63, 63, 70, 0.55)",
} as const;

/**
 * Node styling, keyed by graph node kind.
 *
 * Kind is expressed through stroke, fill and an inner mark rather than through a
 * family of hues, so the graph stays monochrome and a reader can still tell a
 * source from a thread from a consumer.
 */
export interface NodeStyle {
  label: string;
  /** Short form for the compact mobile chip row. */
  short: string;
  fill: string;
  stroke: string;
  halo: string;
  text: string;
  muted: string;
  description: string;
}

export const nodeStyles: Record<
  "source" | "event" | "thread" | "consumer" | "proposal",
  NodeStyle
> = {
  source: {
    label: "Source",
    short: "SRC",
    fill: "#101013",
    stroke: palette.accent,
    halo: "rgba(34, 211, 238, 0.26)",
    text: palette.text,
    muted: palette.textSubtle,
    description: "A system that sent an event into Product.",
  },
  event: {
    label: "Event",
    short: "EVT",
    fill: "#0E0E11",
    stroke: "#A1A1AA",
    halo: "rgba(250, 250, 250, 0.20)",
    text: palette.text,
    muted: palette.textMuted,
    description: "Something that actually happened, as recorded.",
  },
  thread: {
    label: "Thread",
    short: "THR",
    fill: "#0C1416",
    stroke: palette.accentMuted,
    halo: "rgba(103, 232, 249, 0.28)",
    text: "#CFFAFE",
    muted: palette.accentMuted,
    description: "Events that share one correlation id.",
  },
  consumer: {
    label: "Consumer",
    short: "CON",
    fill: "#131316",
    stroke: palette.textFaint,
    halo: "rgba(161, 161, 170, 0.18)",
    text: "#D4D4D8",
    muted: palette.textSubtle,
    description: "A downstream system the event was delivered to.",
  },
  proposal: {
    label: "Proposal",
    short: "PRP",
    fill: "#14141A",
    stroke: "#A5B4FC",
    halo: "rgba(165, 180, 252, 0.24)",
    text: "#E0E7FF",
    muted: "#A5B4FC",
    description: "Something the Brain proposed for a decision.",
  },
};

export const edgeStyles: Record<
  "emitted" | "threaded" | "delivered" | "proposed",
  { stroke: string; width: number; dash?: string }
> = {
  emitted: { stroke: "rgba(161, 161, 170, 0.30)", width: 1 },
  threaded: { stroke: "rgba(103, 232, 249, 0.36)", width: 1.25 },
  delivered: { stroke: "rgba(34, 211, 238, 0.28)", width: 1 },
  proposed: { stroke: "rgba(165, 180, 252, 0.30)", width: 1.25, dash: "3 3" },
};

export const edgeLabels: Record<
  "emitted" | "threaded" | "delivered" | "proposed",
  string
> = {
  emitted: "emitted",
  threaded: "in thread with",
  delivered: "delivered to",
  proposed: "proposed",
};
