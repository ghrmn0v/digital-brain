import type { ConnectomeNodeDto } from "@/modules/connectome";
import type { Point } from "@/components/connectome/force";

/**
 * Greedy label placement.
 *
 * A force graph will happily place two labels on top of each other, and a map
 * whose text is unreadable is worse than a map with no text. This walks the
 * nodes in order of importance and keeps a label only if its box does not
 * collide with one already placed, so the most meaningful names survive and the
 * rest are reachable on hover instead.
 *
 * Deterministic: no randomness, ties broken by id, so the same graph labels
 * itself the same way every render.
 */

export interface LabelBox {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  /** Anchor the label drew from, used to draw the leader line. */
  anchor: Point;
  offsetY: number;
}

const CHARACTER_WIDTH = 6.1;
const LABEL_HEIGHT = 13;
const PADDING = 3;

export function measureLabel(text: string): { width: number; height: number } {
  return {
    width: Math.min(190, text.length * CHARACTER_WIDTH + 8),
    height: LABEL_HEIGHT,
  };
}

function overlaps(a: LabelBox, b: LabelBox): boolean {
  return (
    a.x - PADDING < b.x + b.width + PADDING &&
    a.x + a.width + PADDING > b.x - PADDING &&
    a.y - PADDING < b.y + b.height + PADDING &&
    a.y + a.height + PADDING > b.y - PADDING
  );
}

/**
 * Rank nodes for label priority: the selection and its neighbourhood first,
 * then structural nodes that name a whole group, then the busiest events.
 */
function priority(
  node: ConnectomeNodeDto,
  rank: Map<string, number>,
  kindRank: Record<string, number>,
): number {
  const base = rank.get(node.id);
  if (base !== undefined) return base;
  return 100 + kindRank[node.kind] * 10 + node.weight * 5;
}

export function placeLabels(options: {
  nodes: ConnectomeNodeDto[];
  positions: Map<string, Point>;
  radiusOf: (node: ConnectomeNodeDto) => number;
  emphasis: Set<string>;
  /** How many labels may be drawn before the graph is considered too busy. */
  limit?: number;
  /**
   * The surface the labels are drawn on. A label that would hang over an edge
   * is not clipped by the SVG, it overflows the page and gives the document a
   * horizontal scrollbar, so anything that does not fit is simply not drawn.
   */
  bounds?: { width: number; height: number };
}): Map<string, LabelBox> {
  const { nodes, positions, radiusOf, emphasis, limit = 26, bounds } = options;
  const kindRank: Record<string, number> = {
    source: 0,
    thread: 1,
    consumer: 2,
    proposal: 3,
    event: 4,
  };
  const rank = new Map<string, number>();
  for (const id of emphasis) rank.set(id, 0);

  const ordered = [...nodes].sort((left, right) => {
    const difference =
      priority(left, rank, kindRank) - priority(right, rank, kindRank);
    if (difference !== 0) return difference;
    return left.id.localeCompare(right.id);
  });

  const placed = new Map<string, LabelBox>();
  for (const node of ordered) {
    if (placed.size >= limit) break;
    const point = positions.get(node.id);
    if (!point) continue;
    void radiusOf(node);

    const text = node.label.length > 26 ? `${node.label.slice(0, 25)}…` : node.label;
    const { width, height } = measureLabel(text);
    const radius = radiusOf(node);

    // Try below the node first, then above, then to each side. A label that
    // cannot find a free slot anywhere is simply not drawn.
    const candidates = [
      { dx: 0, dy: radius + 13 },
      { dx: 0, dy: -(radius + 13 + height) },
      { dx: radius + 8, dy: -height / 2 },
      { dx: -(radius + 8 + width), dy: -height / 2 },
    ];

    for (const candidate of candidates) {
      const box: LabelBox = {
        id: node.id,
        x: point.x + candidate.dx - (candidate.dx < 0 ? 0 : width / 2),
        y: point.y + candidate.dy,
        width,
        height,
        anchor: point,
        offsetY: candidate.dy,
      };
      if (bounds) {
        const margin = 4;
        if (
          box.x < margin ||
          box.y < margin ||
          box.x + box.width > bounds.width - margin ||
          box.y + box.height > bounds.height - margin
        ) {
          continue;
        }
      }
      if ([...placed.values()].some((other) => overlaps(box, other))) continue;
      // A label that runs across a node circle is just as unreadable as one
      // that runs across another label, so the discs count as obstacles too.
      const crossesNode = nodes.some((other) => {
        const centre = positions.get(other.id);
        if (!centre) return false;
        const otherRadius = radiusOf(other);
        const nearestX = Math.max(box.x, Math.min(centre.x, box.x + box.width));
        const nearestY = Math.max(box.y, Math.min(centre.y, box.y + box.height));
        return Math.hypot(centre.x - nearestX, centre.y - nearestY) < otherRadius + 1;
      });
      if (crossesNode) continue;
      placed.set(node.id, box);
      break;
    }
  }

  return placed;
}
