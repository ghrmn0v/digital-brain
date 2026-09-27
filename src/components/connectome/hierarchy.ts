import type { ConnectomeEdgeDto, ConnectomeNodeDto } from "@/modules/connectome";

/**
 * Hub-and-spoke hierarchy for the map.
 *
 * The force layout was producing one undifferentiated cloud: every event was
 * equidistant from every other, so the map showed activity without showing
 * structure — you could not see that four of the five nodes were people data and
 * one was a calendar entry. This puts a single "Main Brain" root at the centre
 * and hangs the real nodes off three category hubs, so the shape of the data is
 * legible before you read a single label.
 *
 * The categories are derived from the `source` each event actually came from,
 * not from anything invented at render time. A source that matches nothing falls
 * into the residual category rather than being dropped, so nothing is ever lost
 * by summarising: `hubbed` covers every input node exactly once.
 */

export const ROOT_ID = "hub:main-brain";

interface Category {
  id: string;
  label: string;
  /** Sources that belong here, matched case-insensitively as substrings. */
  sources: string[];
  kind: ConnectomeNodeDto["kind"];
}

/**
 * Ordered so the busiest, most human category is first and the residual is
 * last — an unlabelled bucket should never be the first thing a reader sees.
 */
const CATEGORIES: Category[] = [
  {
    id: "hub:people",
    label: "People & Contacts",
    sources: ["linkedin", "people", "contact"],
    kind: "thread",
  },
  {
    id: "hub:conversations",
    label: "Conversations & Meetings",
    sources: ["whatsapp", "telegram", "slack", "calendar", "meeting", "email"],
    kind: "thread",
  },
  {
    id: "hub:tasks",
    label: "Tasks & Proposals",
    sources: ["core_brain", "task", "proposal", "automation", "fly"],
    kind: "proposal",
  },
];

const RESIDUAL: Category = {
  id: "hub:other",
  label: "Other activity",
  sources: [],
  kind: "consumer",
};

/**
 * The event's originating system.
 *
 * `ConnectomeNodeDto` has no `source` field: the service carries it as a
 * `Source` signal alongside the other provenance, so that is where it is read
 * from. A node with no such signal falls into the residual category rather than
 * being guessed at.
 */
export function sourceOf(node: ConnectomeNodeDto): string {
  const signal = node.signals?.find(
    (candidate) => candidate.label.toLowerCase() === "source",
  );
  return signal?.value ?? "";
}

function categoryFor(source: string): Category {
  const haystack = (source ?? "").toLowerCase();
  for (const category of CATEGORIES) {
    if (category.sources.some((needle) => haystack.includes(needle))) return category;
  }
  return RESIDUAL;
}

export interface HierarchicalGraph {
  nodes: ConnectomeNodeDto[];
  edges: ConnectomeEdgeDto[];
  /** Node id -> the hub it hangs from, excluding the root. */
  hubOf: Map<string, string>;
}

function hubNode(category: Category, count: number): ConnectomeNodeDto {
  return {
    id: category.id,
    kind: category.kind,
    label: category.label,
    detail: `${count} ${count === 1 ? "record" : "records"}`,
    occurredAt: null,
    weight: Math.min(1, 0.55 + count * 0.08),
    signals: [],
    href: null,
  };
}

function link(id: string, source: string, target: string): ConnectomeEdgeDto {
  return { id: `hub:${source}->${target}`, source, target, kind: "threaded", status: null };
}

/**
 * Build the root, the hubs that are actually needed, and the edges that join
 * them. Hubs with no members are omitted so the map never shows an empty
 * category, and the root is omitted entirely when there is nothing to show.
 */
export function buildHierarchy(
  nodes: ConnectomeNodeDto[],
  edges: ConnectomeEdgeDto[],
): HierarchicalGraph {
  if (nodes.length === 0) return { nodes, edges, hubOf: new Map() };

  const buckets = new Map<string, ConnectomeNodeDto[]>();
  for (const node of nodes) {
    const category = categoryFor(sourceOf(node));
    const list = buckets.get(category.id) ?? [];
    list.push(node);
    buckets.set(category.id, list);
  }

  const ordered = [...CATEGORIES, RESIDUAL].filter((category) =>
    buckets.has(category.id),
  );

  const root: ConnectomeNodeDto = {
    id: ROOT_ID,
    kind: "source",
    label: "Main Brain",
    detail: `${nodes.length} ${nodes.length === 1 ? "record" : "records"} across ${ordered.length} ${ordered.length === 1 ? "category" : "categories"}`,
    occurredAt: null,
    weight: 1,
    signals: [],
    href: null,
  };

  const hubOf = new Map<string, string>();
  const syntheticNodes: ConnectomeNodeDto[] = [root];
  const syntheticEdges: ConnectomeEdgeDto[] = [];
  const structuralIds = new Set<string>([ROOT_ID]);

  for (const category of ordered) {
    const members = buckets.get(category.id) ?? [];
    if (members.length === 0) continue;
    const hub = hubNode(category, members.length);
    syntheticNodes.push(hub);
    structuralIds.add(hub.id);
    syntheticEdges.push(link(ROOT_ID, ROOT_ID, hub.id));
    for (const member of members) {
      hubOf.set(member.id, hub.id);
      syntheticEdges.push(link(hub.id, hub.id, member.id));
    }
  }

  // Real edges between real nodes are kept; anything touching a synthetic node
  // would be a duplicate of the spokes just added.
  const realEdges = edges.filter(
    (edge) => !structuralIds.has(edge.source) && !structuralIds.has(edge.target),
  );

  return {
    nodes: [...syntheticNodes, ...nodes],
    edges: [...syntheticEdges, ...realEdges],
    hubOf,
  };
}
