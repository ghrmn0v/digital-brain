import { z } from "zod";

/**
 * The Connectome is a read projection over tables Product already owns.
 *
 * Every node and edge below is derived from a stored column. Nothing is
 * synthesised: a "source" node exists because an event row carries that source,
 * a "thread" node exists because a row's metadata carries that correlation id,
 * and a "consumer" node exists because a delivery row names that consumer. If a
 * relationship is not in the database it is not drawn.
 *
 * This is deliberately *not* the Brain read adapter that `/memory` and
 * `/people` still lack. Those pages show memories and people the Core Brain
 * owns; Product has no read path for them and says so. The Connectome instead
 * shows the event trail Product itself recorded and delivered, which is data
 * this application can read honestly today.
 */

export const CONNECTOME_NODE_KINDS = [
  "source",
  "event",
  "thread",
  "consumer",
  "proposal",
] as const;

export type ConnectomeNodeKind = (typeof CONNECTOME_NODE_KINDS)[number];

export const connectomeQuerySchema = z.object({
  limit: z.coerce.number().int().min(1).max(500).default(160),
  source: z.string().trim().min(1).max(64).optional(),
});

/** Why an event matters, taken from columns that already exist. */
export interface ConnectomeSignal {
  label: string;
  value: string;
}

export interface ConnectomeNodeDto {
  id: string;
  kind: ConnectomeNodeKind;
  /** Short human label. Falls back to the raw type when nothing better exists. */
  label: string;
  /** One line of real supporting text, or null when the row has none. */
  detail: string | null;
  /** ISO timestamp, or null for structural nodes like sources and consumers. */
  occurredAt: string | null;
  /** Relative size hint in 0..1, derived from real degree/payload size. */
  weight: number;
  signals: ConnectomeSignal[];
  /** Where this node can be seen in full, when a real page exists. */
  href: string | null;
}

export type ConnectomeEdgeKind =
  | "emitted"
  | "threaded"
  | "delivered"
  | "proposed";

export interface ConnectomeEdgeDto {
  id: string;
  source: string;
  target: string;
  kind: ConnectomeEdgeKind;
  /** Real status text from the delivery/proposal row, when there is one. */
  status: string | null;
}

export interface ConnectomeGraphDto {
  nodes: ConnectomeNodeDto[];
  edges: ConnectomeEdgeDto[];
  /** Distinct real sources, for the Sources filter. Never invented. */
  sources: string[];
  /** True when no event has ever been received, so the UI can explain why. */
  isEmpty: boolean;
  /** Total events available before the limit, so the UI can be honest. */
  eventCount: number;
  /** Oldest and newest real event timestamps, or null when there are none. */
  range: { from: string | null; to: string | null };
}
