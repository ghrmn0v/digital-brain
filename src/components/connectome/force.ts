import type { ConnectomeEdgeDto, ConnectomeNodeDto } from "@/modules/connectome";

/**
 * A small force-directed layout, written here rather than pulled in.
 *
 * The graph is a few dozen nodes at most, so a library would cost more in
 * bundle and in control than it saves. This is a plain repulsion plus spring
 * model with a fixed number of steps and a cooling schedule: deterministic,
 * because every node starts from a position derived from its own id rather than
 * a random one, so the same data always lays out the same way. A demo that
 * reshuffles itself on every render is not a map of anything.
 *
 * Positions are in graph space; the component applies its own zoom and pan.
 */

export interface Point {
  x: number;
  y: number;
}

export interface SimulationNode extends Point {
  id: string;
  /** Mass grows with real degree so hubs drift less than leaves. */
  mass: number;
  vx: number;
  vy: number;
  /** Fixed by the simulation, used for hit testing and label placement. */
  pinned: boolean;
}

export interface SimulationOptions {
  width: number;
  height: number;
  repulsion?: number;
  springLength?: number;
  springStrength?: number;
  damping?: number;
  centerStrength?: number;
  iterations?: number;
}

/** A stable per-id offset, so layout is reproducible across renders and runs. */
function seedFor(id: string): number {
  let hash = 2166136261;
  for (let index = 0; index < id.length; index += 1) {
    hash ^= id.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  // Map into [0, 1) without Math.random: the same id always starts in the
  // same place, which is what makes the layout feel like a place.
  return ((hash >>> 0) % 100000) / 100000;
}

function place(id: string, width: number, height: number, index: number, total: number): Point {
  const angle = seedFor(id) * Math.PI * 2;
  // Spread the starting ring by index as well, so a graph of ids that hash
  // into the same sector still begins untangled.
  const spread = total > 1 ? (index / total) * Math.PI * 2 : 0;
  const radius = Math.min(width, height) * (0.22 + 0.14 * seedFor(`${id}#r`));
  return {
    x: width / 2 + Math.cos(angle + spread) * radius,
    y: height / 2 + Math.sin(angle + spread) * radius,
  };
}

export function createSimulation(
  nodes: ConnectomeNodeDto[],
  edges: ConnectomeEdgeDto[],
  options: SimulationOptions,
): SimulationNode[] {
  const {
    width,
    height,
    repulsion = 5200,
    springLength = 108,
    springStrength = 0.045,
    damping = 0.82,
    centerStrength = 0.014,
    iterations = 320,
  } = options;

  const degree = new Map<string, number>();
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }

  const simulation: SimulationNode[] = nodes.map((node, index) => {
    const start = place(node.id, width, height, index, nodes.length);
    return {
      id: node.id,
      x: start.x,
      y: start.y,
      vx: 0,
      vy: 0,
      mass: 1 + Math.min(6, degree.get(node.id) ?? 0),
      pinned: false,
    };
  });

  const byId = new Map(simulation.map((node) => [node.id, node]));
  const springs = edges
    .map((edge) => ({
      from: byId.get(edge.source),
      to: byId.get(edge.target),
    }))
    .filter(
      (pair): pair is { from: SimulationNode; to: SimulationNode } =>
        Boolean(pair.from && pair.to),
    );

  for (let step = 0; step < iterations; step += 1) {
    const alpha = Math.max(0.02, 1 - step / iterations);

    for (let i = 0; i < simulation.length; i += 1) {
      for (let j = i + 1; j < simulation.length; j += 1) {
        const a = simulation[i];
        const b = simulation[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distanceSquared = dx * dx + dy * dy;
        if (distanceSquared < 0.01) {
          // Coincident nodes get a deterministic nudge apart instead of a
          // random one, so the result stays reproducible.
          dx = (seedFor(a.id) - 0.5) * 2;
          dy = (seedFor(b.id) - 0.5) * 2;
          distanceSquared = dx * dx + dy * dy;
        }
        const distance = Math.sqrt(distanceSquared);
        const force = (repulsion * alpha) / distanceSquared;
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        a.vx -= fx / a.mass;
        a.vy -= fy / a.mass;
        b.vx += fx / b.mass;
        b.vy += fy / b.mass;
      }
    }

    for (const spring of springs) {
      const dx = spring.to.x - spring.from.x;
      const dy = spring.to.y - spring.from.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const displacement = distance - springLength;
      const force = displacement * springStrength * alpha;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      spring.from.vx += fx / spring.from.mass;
      spring.from.vy += fy / spring.from.mass;
      spring.to.vx -= fx / spring.to.mass;
      spring.to.vy -= fy / spring.to.mass;
    }

    for (const node of simulation) {
      node.vx += (width / 2 - node.x) * centerStrength * alpha * node.mass;
      node.vy += (height / 2 - node.y) * centerStrength * alpha * node.mass;
      node.vx *= damping;
      node.vy *= damping;
      if (!node.pinned) {
        node.x += Math.max(-18, Math.min(18, node.vx));
        node.y += Math.max(-18, Math.min(18, node.vy));
      }
    }
  }

  return simulation;
}

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export function boundsOf(points: Point[]): Bounds {
  if (points.length === 0) {
    return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  }
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const point of points) {
    if (point.x < minX) minX = point.x;
    if (point.y < minY) minY = point.y;
    if (point.x > maxX) maxX = point.x;
    if (point.y > maxY) maxY = point.y;
  }
  return { minX, minY, maxX, maxY };
}

/** Radius from the node's real weight, so importance is visible but restrained. */
export function radiusFor(node: ConnectomeNodeDto): number {
  const base = node.kind === "event" ? 8.5 : node.kind === "thread" ? 7 : 6;
  return base + node.weight * 9;
}

export function neighboursOf(
  edges: ConnectomeEdgeDto[],
  nodeId: string,
): Set<string> {
  const found = new Set<string>();
  for (const edge of edges) {
    if (edge.source === nodeId) found.add(edge.target);
    if (edge.target === nodeId) found.add(edge.source);
  }
  return found;
}
