"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  BrainCircuit,
  CircleDot,
  GitBranch,
  Info,
  Layers,
  MessageSquareText,
  Radio,
} from "lucide-react";
import type {
  ConnectomeEdgeDto,
  ConnectomeNodeDto,
} from "@/modules/connectome";
import { edgeLabels, edgeStyles, nodeStyles } from "@/components/connectome/theme";
import { formatDateTime, formatRelativeTime } from "@/lib/client/format";

/**
 * The intelligence panel: what the system actually knows about the selection.
 *
 * Every line here is a stored value. There is no summary written here, because
 * Product cannot read the Brain's understanding to produce one, and a panel that
 * sounds like it knows things while sourcing them from nowhere is worse than a
 * panel that admits the limit. Where a section would need data the product does
 * not have, it says so instead of filling the space.
 */

export function ConnectomeInspector({
  node,
  nodes,
  edges,
  now,
}: {
  node: ConnectomeNodeDto | null;
  nodes: ConnectomeNodeDto[];
  edges: ConnectomeEdgeDto[];
  now: Date;
}) {
  if (!node) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 py-10 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/60 text-zinc-450">
          <GitBranch aria-hidden="true" className="h-5 w-5" />
        </span>
        <h2 className="mt-4 text-sm font-semibold text-zinc-200">
          Select a node to explore its context.
        </h2>
        <p className="mt-1.5 max-w-[16rem] text-xs leading-5 text-zinc-450">
          The map is drawn from events this device has actually recorded. Pick a
          node to see where it came from and where it went.
        </p>
      </div>
    );
  }

  const style = nodeStyles[node.kind];
  const byId = new Map(nodes.map((candidate) => [candidate.id, candidate]));

  const related = edges
    .filter((edge) => edge.source === node.id || edge.target === node.id)
    .map((edge) => {
      const otherId = edge.source === node.id ? edge.target : edge.source;
      return {
        edge,
        direction: edge.source === node.id ? "out" : "in",
        other: byId.get(otherId) ?? null,
      };
    })
    .filter((entry): entry is { edge: ConnectomeEdgeDto; direction: "in" | "out"; other: ConnectomeNodeDto } =>
      Boolean(entry.other),
    );

  const incoming = related.filter((entry) => entry.direction === "in");
  const outgoing = related.filter((entry) => entry.direction === "out");

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="border-b border-zinc-800/70 px-4 py-4">
        <div className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{
              borderColor: style.stroke,
              color: style.stroke,
              backgroundColor: `${style.stroke}14`,
            }}
          >
            <CircleDot className="h-2.5 w-2.5" />
            {style.label}
          </span>
        </div>
        <h2 className="mt-2.5 break-words text-base font-semibold leading-6 text-white">
          {node.label}
        </h2>
        <p className="mt-1 text-xs leading-5 text-zinc-450">{style.description}</p>
      </header>

      {node.detail ? (
        <p className="border-b border-zinc-800/70 px-4 py-3 text-sm leading-6 text-zinc-300">
          {node.detail}
        </p>
      ) : null}

      <InspectorSection title="Node" icon={Info}>
        <dl className="space-y-2">
          <Row term="Type" value={style.label} />
          <Row term="ID" value={node.id} mono />
          {node.occurredAt ? (
            <>
              <Row term="Occurred" value={formatDateTime(node.occurredAt)} />
              <Row term="Relative" value={formatRelativeTime(node.occurredAt, now)} />
            </>
          ) : null}
          <Row term="Connections" value={String(related.length)} />
        </dl>
      </InspectorSection>

      <InspectorSection title="Context" icon={Layers}>
        {node.signals.length > 0 ? (
          <dl className="space-y-2">
            {node.signals.map((signal) => (
              <Row
                key={`${signal.label}-${signal.value}`}
                term={signal.label}
                value={signal.value}
                mono={signal.label === "Thread" || signal.label === "File"}
              />
            ))}
          </dl>
        ) : (
          <p className="text-xs leading-5 text-zinc-450">
            This node carries no additional stored fields.
          </p>
        )}
      </InspectorSection>

      <InspectorSection title="Relationships" icon={GitBranch}>
        {related.length === 0 ? (
          <p className="text-xs leading-5 text-zinc-450">
            Nothing else in the graph references this node yet.
          </p>
        ) : (
          <div className="space-y-4">
            <RelationshipGroup heading="Connected from" entries={incoming} />
            <RelationshipGroup heading="Connected to" entries={outgoing} />
          </div>
        )}
      </InspectorSection>

      <InspectorSection title="AI understanding" icon={BrainCircuit}>
        <p className="text-xs leading-5 text-zinc-450">
          The Core Brain does the understanding, and Product cannot read its
          memories yet. What you see above is the recorded event, not a summary
          the Brain wrote about it.
        </p>
        <Link
          href="/memory"
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 transition hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
        >
          See the memory boundary
          <ArrowUpRight aria-hidden="true" className="h-3.5 w-3.5" />
        </Link>
      </InspectorSection>

      <div className="space-y-2 border-t border-zinc-800/70 p-4">
        <Link
          href={`/chat?context=${encodeURIComponent(
            `${nodeStyles[node.kind].label}: ${node.label}`,
          )}`}
          className="inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-lg border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-300/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
        >
          <MessageSquareText aria-hidden="true" className="h-3.5 w-3.5" />
          Ask about this
        </Link>
        {node.href ? (
          <Link
            href={node.href}
            className="inline-flex min-h-9 w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900/70 px-3 py-2 text-xs font-semibold text-zinc-200 transition hover:border-zinc-600 hover:bg-zinc-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
          >
            Open {node.href === "/connectors" ? "connectors" : node.href.slice(1)}
            <ArrowUpRight aria-hidden="true" className="h-3.5 w-3.5" />
          </Link>
        ) : null}
      </div>
      {!node.href ? (
        <p className="border-t border-zinc-800/70 px-4 py-3 text-[11px] leading-5 text-zinc-550">
          <Radio aria-hidden="true" className="mr-1 inline h-3 w-3" />
          No screen exists for this kind of record, so there is nothing to open.
        </p>
      ) : null}
    </div>
  );
}

function InspectorSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Info;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-zinc-800/70 px-4 py-3.5">
      <h3 className="mb-2.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-450">
        <Icon aria-hidden="true" className="h-3 w-3" />
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({
  term,
  value,
  mono,
}: {
  term: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-[11px] uppercase tracking-[0.1em] text-zinc-550">
        {term}
      </dt>
      <dd
        className={`min-w-0 break-words text-right text-xs text-zinc-300 ${
          mono ? "font-mono text-[11px]" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function RelationshipGroup({
  heading,
  entries,
}: {
  heading: string;
  entries: Array<{
    edge: ConnectomeEdgeDto;
    direction: "in" | "out";
    other: ConnectomeNodeDto;
  }>;
}) {
  if (entries.length === 0) return null;
  return (
    <div>
      <p className="mb-1.5 text-[11px] text-zinc-550">{heading}</p>
      <ul className="space-y-1.5">
        {entries.map(({ edge, other }) => (
          <li
            key={`${edge.kind}-${other.id}`}
            className="flex items-center gap-2 text-xs"
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: edgeStyles[edge.kind].stroke }}
            />
            <span className="truncate text-zinc-400">
              {edgeLabels[edge.kind]}
            </span>
            <span className="min-w-0 flex-1 truncate text-zinc-200">
              {other.label}
            </span>
            {edge.status ? (
              <span className="shrink-0 text-[10px] uppercase tracking-wider text-zinc-550">
                {edge.status.toLowerCase()}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
