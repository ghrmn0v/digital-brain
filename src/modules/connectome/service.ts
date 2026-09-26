import "server-only";

import { prisma } from "@/lib/prisma";
import type {
  ConnectomeEdgeDto,
  ConnectomeEdgeKind,
  ConnectomeGraphDto,
  ConnectomeNodeDto,
  ConnectomeNodeKind,
  ConnectomeSignal,
} from "@/modules/connectome/contracts";

/**
 * Project Product's own event trail into a graph.
 *
 * The shape is deliberately shallow and entirely derived:
 *
 *   source ──emitted──▶ event ──threaded──▶ thread
 *                          │
 *                          ├──delivered──▶ consumer   (from EventDelivery rows)
 *                          └──proposed───▶ proposal  (from DeveloperProposal rows)
 *
 * Each arrow is one stored column. A thread node appears only when a real
 * correlation id exists, and disappears again when it would have exactly one
 * member, because a node with a single unremarkable edge tells the user
 * nothing. Nothing here infers a person, a project or a topic: the Brain owns
 * that understanding and Product cannot read it yet.
 */

const MAX_LABEL = 72;

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readNumber(source: Record<string, unknown>, key: string): number | null {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function truncate(value: string, limit = MAX_LABEL): string {
  const single = value.replace(/\s+/g, " ").trim();
  if (single.length <= limit) return single;
  return `${single.slice(0, Math.max(1, limit - 1))}…`;
}

/**
 * A readable label for an event, built only from fields the row actually has.
 *
 * The event `type` is the reliable part; payload fields are opportunistic, so
 * an event that carries a message or a job title shows something a person can
 * recognise instead of a bare `message.received`.
 */
function labelForEvent(type: string, payload: unknown): string {
  const data = isRecord(payload) ? payload : {};
  const candidates = [
    readString(data, "summary"),
    readString(data, "title"),
    readString(data, "text"),
    readString(data, "name"),
    readString(data, "description"),
  ].filter((value): value is string => value !== null);

  if (candidates.length === 0) return type;
  const best = candidates.sort((left, right) => right.length - left.length)[0];
  return truncate(best);
}

function detailForEvent(payload: unknown): string | null {
  const data = isRecord(payload) ? payload : {};
  const parts: string[] = [];

  const company = readString(data, "company");
  const location = readString(data, "location");
  if (company && location) parts.push(`${company} · ${location}`);
  else if (company) parts.push(company);
  else if (location) parts.push(location);

  const file = readString(data, "file");
  if (file) parts.push(file);

  const finding = readString(data, "finding") ?? readString(data, "title");
  if (finding && file) parts.push(truncate(finding, 90));

  const text = readString(data, "text");
  if (text && parts.length === 0) return truncate(text, 140);

  return parts.length ? truncate(parts.join(" · "), 140) : null;
}

/** Real, already-stored facts about an event. No model output is invented. */
function signalsForEvent(
  type: string,
  timestamp: Date,
  payload: unknown,
  correlationId: string | null,
): ConnectomeSignal[] {
  const data = isRecord(payload) ? payload : {};
  const signals: ConnectomeSignal[] = [
    { label: "Type", value: type },
    { label: "Received", value: timestamp.toISOString() },
  ];

  if (correlationId) signals.push({ label: "Thread", value: correlationId });

  const confidence = readNumber(data, "confidence");
  if (confidence !== null) {
    signals.push({
      label: "Confidence",
      value: confidence.toFixed(2),
    });
  }

  const severity = readString(data, "severity");
  if (severity) signals.push({ label: "Severity", value: severity });

  const file = readString(data, "file");
  if (file) {
    signals.push({
      label: "File",
      value: `${file}${readNumber(data, "line") !== null ? `:${data.line}` : ""}`,
    });
  }

  const topics = data.topics;
  if (Array.isArray(topics) && topics.length > 0) {
    const names = topics
      .map((topic) => (typeof topic === "string" ? topic : null))
      .filter((topic): topic is string => Boolean(topic));
    if (names.length) {
      signals.push({ label: "Topics", value: names.slice(0, 4).join(", ") });
    }
  }

  return signals;
}

/** The correlation id a row really carries, from either metadata or payload. */
function correlationOf(
  metadata: unknown,
  payload: unknown,
): string | null {
  const meta = isRecord(metadata) ? metadata : {};
  const data = isRecord(payload) ? payload : {};
  return (
    readString(meta, "correlationId") ??
    readString(meta, "correlation_id") ??
    readString(data, "correlation_id") ??
    readString(data, "correlationId")
  );
}

function titleCase(value: string): string {
  return value
    .split(/[._\-\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

interface EventRow {
  id: string;
  eventId: string;
  source: string;
  type: string;
  timestamp: Date;
  payload: unknown;
  metadata: unknown;
  deliveries: Array<{ consumer: string; status: string; attempts: number }>;
  developerProposal: { id: string; status: string } | null;
}

export const connectomeService = {
  async graph(options: { limit?: number; source?: string } = {}): Promise<ConnectomeGraphDto> {
    const limit = options.limit ?? 160;

    const rows = (await prisma.integrationEvent.findMany({
      orderBy: { createdAt: "desc" },
      take: limit,
      include: {
        deliveries: {
          select: { consumer: true, status: true, attempts: true },
        },
        developerProposal: {
          select: { id: true, status: true },
        },
      },
    })) as EventRow[];

    const eventCount = await prisma.integrationEvent.count();
    const allSources = (
      await prisma.integrationEvent.findMany({
        select: { source: true },
        distinct: ["source"],
        orderBy: { source: "asc" },
      })
    ).map((row) => row.source);

    if (rows.length === 0) {
      return {
        nodes: [],
        edges: [],
        sources: allSources,
        isEmpty: true,
        eventCount,
        range: { from: null, to: null },
      };
    }

    const visible = options.source
      ? rows.filter((row) => row.source === options.source)
      : rows;

    const nodes: ConnectomeNodeDto[] = [];
    const edges: ConnectomeEdgeDto[] = [];
    const seen = new Set<string>();

    const addNode = (node: ConnectomeNodeDto) => {
      if (seen.has(node.id)) return;
      seen.add(node.id);
      nodes.push(node);
    };

    const addEdge = (
      edge: ConnectomeEdgeDto,
    ) => {
      const key = `${edge.kind}:${edge.source}->${edge.target}`;
      if (edges.some((existing) => `${existing.kind}:${existing.source}->${existing.target}` === key)) {
        return;
      }
      edges.push(edge);
    };

    // Thread membership, so a thread with one event can be skipped entirely.
    const threadMembers = new Map<string, string[]>();
    for (const row of visible) {
      const correlationId = correlationOf(row.metadata, row.payload);
      if (!correlationId) continue;
      const bucket = threadMembers.get(correlationId) ?? [];
      bucket.push(row.id);
      threadMembers.set(correlationId, bucket);
    }

    // A node's prominence is its real degree in the graph, nothing else.
    const degree = new Map<string, number>();
    const bump = (id: string) => degree.set(id, (degree.get(id) ?? 0) + 1);

    for (const row of visible) {
      const correlationId = correlationOf(row.metadata, row.payload);
      const eventNodeId = `event:${row.id}`;

      // source ──▶ event
      const sourceNodeId = `source:${row.source}`;
      addNode({
        id: sourceNodeId,
        kind: "source",
        label: titleCase(row.source),
        detail: `${rows.filter((other) => other.source === row.source).length} events in view`,
        occurredAt: null,
        weight: 0.5,
        signals: [{ label: "Source", value: row.source }],
        href: "/connectors",
      });
      addEdge({
        id: `edge:emitted:${sourceNodeId}->${eventNodeId}`,
        source: sourceNodeId,
        target: eventNodeId,
        kind: "emitted",
        status: null,
      });
      bump(sourceNodeId);
      bump(eventNodeId);

      // event ──▶ thread
      if (correlationId && (threadMembers.get(correlationId)?.length ?? 0) > 1) {
        const threadNodeId = `thread:${correlationId}`;
        addNode({
          id: threadNodeId,
          kind: "thread",
          label: truncate(correlationId, 40),
          detail: `${threadMembers.get(correlationId)?.length ?? 0} events share this thread`,
          occurredAt: null,
          weight: 0.62,
          signals: [
            { label: "Thread", value: correlationId },
            {
              label: "Members",
              value: String(threadMembers.get(correlationId)?.length ?? 0),
            },
          ],
          href: null,
        });
        addEdge({
          id: `edge:threaded:${eventNodeId}->${threadNodeId}`,
          source: eventNodeId,
          target: threadNodeId,
          kind: "threaded",
          status: null,
        });
        bump(threadNodeId);
      }

      // event ──▶ consumer, once per real delivery row
      for (const delivery of row.deliveries) {
        const consumerNodeId = `consumer:${delivery.consumer}`;
        addNode({
          id: consumerNodeId,
          kind: "consumer",
          label: titleCase(delivery.consumer),
          detail:
            delivery.status === "DELIVERED"
              ? "Received this event"
              : `Delivery ${delivery.status.toLowerCase()}`,
          occurredAt: null,
          weight: 0.44,
          signals: [
            { label: "Consumer", value: delivery.consumer },
            { label: "Status", value: delivery.status },
            { label: "Attempts", value: String(delivery.attempts) },
          ],
          href: null,
        });
        addEdge({
          id: `edge:delivered:${eventNodeId}->${consumerNodeId}`,
          source: eventNodeId,
          target: consumerNodeId,
          kind: "delivered",
          status: delivery.status,
        });
        bump(consumerNodeId);
      }

      // event ──▶ proposal, only when the row really has one
      if (row.developerProposal) {
        const proposalNodeId = `proposal:${row.developerProposal.id}`;
        addNode({
          id: proposalNodeId,
          kind: "proposal",
          label: "Proposal",
          detail: `Awaiting a decision · ${row.developerProposal.status.toLowerCase()}`,
          occurredAt: null,
          weight: 0.4,
          signals: [
            { label: "Status", value: row.developerProposal.status },
            { label: "From event", value: row.eventId },
          ],
          href: "/developer",
        });
        addEdge({
          id: `edge:proposed:${eventNodeId}->${proposalNodeId}`,
          source: eventNodeId,
          target: proposalNodeId,
          kind: "proposed",
          status: row.developerProposal.status,
        });
        bump(proposalNodeId);
      }

      addNode({
        id: eventNodeId,
        kind: "event",
        label: labelForEvent(row.type, row.payload),
        detail: detailForEvent(row.payload),
        occurredAt: row.timestamp.toISOString(),
        weight: 0.7,
        signals: signalsForEvent(row.type, row.timestamp, row.payload, correlationId),
        href: null,
      });
    }

    const maxDegree = Math.max(1, ...degree.values());
    for (const node of nodes) {
      const value = degree.get(node.id) ?? 1;
      node.weight = clamp01(0.32 + (value / maxDegree) * 0.68);
    }

    const timestamps = visible
      .map((row) => row.timestamp.getTime())
      .filter((value) => Number.isFinite(value));
    const from = timestamps.length ? new Date(Math.min(...timestamps)) : null;
    const to = timestamps.length ? new Date(Math.max(...timestamps)) : null;

    return {
      nodes,
      edges,
      sources: allSources,
      isEmpty: false,
      eventCount,
      range: {
        from: from ? from.toISOString() : null,
        to: to ? to.toISOString() : null,
      },
    };
  },
};

export type { ConnectomeNodeKind, ConnectomeEdgeKind };
