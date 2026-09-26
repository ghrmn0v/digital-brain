"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { Maximize2, Minus, Plus } from "lucide-react";
import type { ConnectomeEdgeDto, ConnectomeNodeDto } from "@/modules/connectome";
import {
  createSimulation,
  neighboursOf,
  radiusFor,
  type SimulationNode,
} from "@/components/connectome/force";
import { placeLabels } from "@/components/connectome/labels";
import {
  edgeStyles,
  nodeStyles,
  palette,
  surface,
} from "@/components/connectome/theme";

/**
 * The Connectome canvas.
 *
 * Rendered as SVG rather than WebGL: the graph is tens of nodes, and SVG keeps
 * every node a real focusable element, which is what makes the map usable from
 * a keyboard and readable by a screen reader. Canvas would be faster and would
 * also throw all of that away for no benefit at this size.
 *
 * The simulation is computed once per data change, not per frame, so pan and
 * zoom are pure transforms and cost nothing. `prefers-reduced-motion` removes
 * the transitions; it does not remove the graph.
 */

const MIN_ZOOM = 0.35;
const MAX_ZOOM = 3;

export interface ConnectomeCanvasProps {
  nodes: ConnectomeNodeDto[];
  edges: ConnectomeEdgeDto[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Highlights a node chosen elsewhere, e.g. from the timeline. */
  focusId?: string | null;
  className?: string;
}

interface Viewport {
  zoom: number;
  offsetX: number;
  offsetY: number;
}

export function ConnectomeCanvas({
  nodes,
  edges,
  selectedId,
  onSelect,
  focusId,
  className,
}: ConnectomeCanvasProps) {
  const gradientId = useId().replace(/:/g, "");
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 960, height: 620 });
  // null means "follow the fit". Only a deliberate pan or zoom pins the view,
  // so a newly arrived event re-frames itself instead of landing off-screen.
  const [pinnedView, setPinnedView] = useState<Viewport | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const dragState = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
    onControl: boolean;
  } | null>(null);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  // Measure the region so the layout has a real box to aim for.
  useEffect(() => {
    const element = surfaceRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (!box || box.width < 1 || box.height < 1) return;
      setSize({ width: Math.round(box.width), height: Math.round(box.height) });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const placed = useMemo<SimulationNode[]>(
    () =>
      createSimulation(nodes, edges, {
        width: Math.max(320, size.width),
        height: Math.max(280, size.height),
        // Scaled to the canvas so the map fills the space it is given instead of
        // huddling in the middle of it. A graph that occupies a quarter of the
        // frame reads as a loading state, not as a map.
        repulsion: Math.max(5200, (size.width * size.height) / 240),
        springLength: Math.max(120, Math.min(size.width, size.height) / 5.2),
      }),
    [nodes, edges, size.width, size.height],
  );

  const byId = useMemo(
    () => new Map(placed.map((node) => [node.id, node])),
    [placed],
  );
  const nodeById = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes],
  );

  // The active neighbourhood drives the dimming: everything not connected to
  // the focused node recedes, which is what makes a dense graph readable.
  const focus = hoveredId ?? selectedId ?? focusId;
  const highlighted = useMemo(
    () => (focus ? neighboursOf(edges, focus) : null),
    [edges, focus],
  );

  // The layout is already normalised to this exact box, so the resting view is
  // the identity transform. Computing a second fit on top of it would shrink the
  // map twice - badly enough to make it illegible on a phone, where the canvas
  // is only a few hundred pixels across and a fixed padding is a third of it.
  const fitted = useMemo<Viewport>(
    () => ({ zoom: 1, offsetX: 0, offsetY: 0 }),
    [],
  );

  const viewport = pinnedView ?? fitted;

  const fit = useCallback(() => setPinnedView(null), []);

  // A node chosen elsewhere, e.g. from the timeline, is centred on rather than
  // merely highlighted. Deferred a frame because it needs the laid-out
  // positions, which do not exist until after the browser has measured.
  useEffect(() => {
    if (!focusId) return;
    const target = byId.get(focusId);
    if (!target) return;
    const frame = window.requestAnimationFrame(() => {
      setPinnedView((current) => {
        const base = current ?? fitted;
        return {
          zoom: base.zoom,
          offsetX: size.width / 2 - target.x * base.zoom,
          offsetY: size.height / 2 - target.y * base.zoom,
        };
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [focusId, byId, fitted, size.width, size.height]);

  const zoomBy = useCallback(
    (factor: number) => {
      setPinnedView((current) => {
        const base = current ?? fitted;
        return {
          ...base,
          zoom: Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, base.zoom * factor)),
        };
      });
    },
    [fitted],
  );

  const onWheel = useCallback((event: ReactWheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey && Math.abs(event.deltaY) < 2) return;
    setPinnedView((current) => {
      const base = current ?? { zoom: 1, offsetX: 0, offsetY: 0 };
      return {
        ...base,
        zoom: Math.max(
          MIN_ZOOM,
          Math.min(MAX_ZOOM, base.zoom * (event.deltaY > 0 ? 0.92 : 1.08)),
        ),
      };
    });
  }, []);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    // A press that begins on something interactive belongs to that thing, not to
    // the pan. Capturing the pointer here would retarget the following click to
    // this element, so the target's own handler would never run: tapping a node
    // cleared the selection instead of opening it, and the zoom buttons did
    // nothing at all. Nodes and the overlay controls both count as interactive.
    const onControl = Boolean(
      (event.target as Element | null)?.closest?.(
        'g[role="button"], button, [role="button"], a[href], input',
      ),
    );
    dragState.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: viewport.offsetX,
      originY: viewport.offsetY,
      moved: false,
      onControl,
    };
    if (!onControl) event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragState.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) drag.moved = true;
    setPinnedView((current) => ({
      zoom: current?.zoom ?? 1,
      offsetX: drag.originX + dx,
      offsetY: drag.originY + dy,
    }));
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragState.current;
    dragState.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    // A press on empty canvas that never moved is a click on the background.
    // A press that began on a node or a control is left to its own handler.
    if (drag && !drag.moved && !drag.onControl) onSelect(null);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      zoomBy(1.15);
    } else if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      zoomBy(0.87);
    } else if (event.key === "0") {
      event.preventDefault();
      fit();
    } else if (event.key === "Escape") {
      onSelect(null);
    } else if (event.key === "Tab") {
      // Let Tab do its job: every node is in the tab order already.
      return;
    }
  };

  // Labels are placed against the real positions, emphasised nodes first, and
  // any label that cannot find a free slot is simply not drawn rather than
  // printed on top of another.
  const labelBoxes = useMemo(() => {
    const emphasis = new Set<string>();
    if (focus) {
      emphasis.add(focus);
      for (const id of highlighted ?? []) emphasis.add(id);
    }
    if (selectedId) emphasis.add(selectedId);
    // A phone has a few hundred pixels to spend and every label competes for
    // them, so the budget tightens with the canvas instead of scaling with area:
    // twelve overlapping names are worse than six legible ones plus a tooltip.
    const roomy = size.width >= 640;
    const budget = roomy
      ? Math.max(12, Math.round((size.width * size.height) / 9000))
      : 6;
    return placeLabels({
      nodes,
      positions: byId,
      radiusOf: radiusFor,
      emphasis,
      limit: Math.min(30, budget),
      bounds: { width: size.width, height: size.height },
    });
  }, [nodes, byId, focus, highlighted, selectedId, size.width, size.height]);

  const motion = reducedMotion
    ? ""
    : "transition-[opacity,transform] duration-200 ease-out motion-reduce:transition-none";

  return (
    <div
      ref={surfaceRef}
      className={className}
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onKeyDown={onKeyDown}
      style={{
        backgroundColor: surface.canvas,
        backgroundImage: `radial-gradient(circle at 50% 42%, rgba(34, 211, 238, 0.05), transparent 58%), radial-gradient(circle at 1px 1px, ${surface.grid} 1px, transparent 0)`,
        backgroundSize: "100% 100%, 28px 28px",
        touchAction: "none",
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${size.width} ${size.height}`}
        role="application"
        aria-label={`Connectome graph with ${nodes.length} nodes and ${edges.length} connections`}
        className="block h-full w-full"
      >
        <defs>
          <radialGradient id={`node-glow-${gradientId}`}>
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
          </radialGradient>
        </defs>

        <g
          transform={`translate(${viewport.offsetX} ${viewport.offsetY}) scale(${viewport.zoom})`}
        >
          <g aria-hidden="true">
            {edges.map((edge) => {
              const from = byId.get(edge.source);
              const to = byId.get(edge.target);
              if (!from || !to) return null;
              const style = edgeStyles[edge.kind];
              const active =
                focus !== null &&
                (edge.source === focus || edge.target === focus);
              return (
                <line
                  key={edge.id}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={active ? palette.accent : style.stroke}
                  strokeWidth={active ? style.width + 0.9 : style.width}
                  strokeDasharray={style.dash}
                  strokeLinecap="round"
                  opacity={focus === null ? 1 : active ? 0.95 : 0.16}
                  style={
                    reducedMotion
                      ? undefined
                      : { transition: "opacity 180ms ease, stroke 180ms ease" }
                  }
                />
              );
            })}
          </g>

          {nodes.map((node) => {
            const point = byId.get(node.id);
            if (!point) return null;
            const style = nodeStyles[node.kind];
            const radius = radiusFor(node);
            const isSelected = selectedId === node.id;
            const isFocused = focus === node.id;
            const connected = highlighted?.has(node.id) ?? false;
            const dimmed =
              focus !== null && !isFocused && !connected && !isSelected;

            return (
              <g
                key={node.id}
                transform={`translate(${point.x} ${point.y})`}
                tabIndex={0}
                role="button"
                aria-pressed={isSelected}
                aria-label={`${style.label}: ${node.label}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(isSelected ? null : node.id);
                }}
                onPointerEnter={() => setHoveredId(node.id)}
                onPointerLeave={() =>
                  setHoveredId((current) => (current === node.id ? null : current))
                }
                onFocus={() => setHoveredId(node.id)}
                onBlur={() =>
                  setHoveredId((current) => (current === node.id ? null : current))
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(isSelected ? null : node.id);
                  }
                }}
                className="cursor-pointer outline-none [&:focus-visible>circle:first-of-type]:stroke-cyan-200"
                style={{ opacity: dimmed ? 0.28 : 1, ...(reducedMotion ? {} : { transition: "opacity 200ms ease" }) }}
              >
                {isFocused || isSelected ? (
                  <circle
                    r={radius + 9}
                    fill={`url(#node-glow-${gradientId})`}
                    opacity={isSelected ? 0.55 : 0.3}
                    aria-hidden="true"
                  />
                ) : null}
                <circle
                  r={radius}
                  fill={style.fill}
                  stroke={isSelected ? palette.accent : style.stroke}
                  strokeWidth={isSelected ? 2 : 1.25}
                  aria-hidden="true"
                />
                {node.kind === "thread" ? (
                  <circle
                    r={radius * 0.45}
                    fill="none"
                    stroke={style.stroke}
                    strokeWidth={1}
                    opacity={0.7}
                    aria-hidden="true"
                  />
                ) : null}
                {node.kind === "consumer" ? (
                  <circle
                    r={radius * 0.4}
                    fill={style.stroke}
                    opacity={0.5}
                    aria-hidden="true"
                  />
                ) : null}
              </g>
            );
          })}
        </g>

        {/* Labels are drawn outside the zoom group and positioned in screen
            space on purpose. Inside it they would scale with the map, so
            zooming in would turn 11px text into a billboard and zooming out
            would render it unreadable. */}
        <g aria-hidden="true">
          {nodes.map((node) => {
            const box = labelBoxes.get(node.id);
            if (!box) return null;
            const style = nodeStyles[node.kind];
            const dimmed =
              focus !== null && !highlighted?.has(node.id) && focus !== node.id;
            const text =
              node.label.length > 26 ? `${node.label.slice(0, 25)}…` : node.label;
            return (
              <text
                key={`label-${node.id}`}
                x={(box.x + box.width / 2) * viewport.zoom + viewport.offsetX}
                y={(box.y + box.height - 3) * viewport.zoom + viewport.offsetY}
                textAnchor="middle"
                fontSize={11}
                fill={style.text}
                opacity={dimmed ? 0.4 : 0.95}
                style={{ pointerEvents: "none", userSelect: "none" }}
              >
                {text}
              </text>
            );
          })}
        </g>
      </svg>

      <div className="pointer-events-none absolute right-3 top-3 flex flex-col gap-1.5">
        <CanvasButton label="Zoom in" onClick={() => zoomBy(1.18)}>
          <Plus aria-hidden="true" className="h-3.5 w-3.5" />
        </CanvasButton>
        <CanvasButton label="Zoom out" onClick={() => zoomBy(0.85)}>
          <Minus aria-hidden="true" className="h-3.5 w-3.5" />
        </CanvasButton>
        <CanvasButton label="Fit graph to view" onClick={fit}>
          <Maximize2 aria-hidden="true" className="h-3.5 w-3.5" />
        </CanvasButton>
      </div>

      {focus && nodeById.get(focus) ? (
        <div
          className={`pointer-events-none absolute left-3 top-3 max-w-[min(20rem,70%)] rounded-xl border border-zinc-700/70 bg-zinc-950/85 px-3 py-2 backdrop-blur ${motion}`}
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300/80">
            {nodeStyles[nodeById.get(focus)!.kind].label}
          </p>
          <p className="mt-0.5 truncate text-sm font-medium text-zinc-100">
            {nodeById.get(focus)!.label}
          </p>
          {nodeById.get(focus)!.detail ? (
            <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-zinc-400">
              {nodeById.get(focus)!.detail}
            </p>
          ) : null}
        </div>
      ) : null}

      <p className="pointer-events-none absolute bottom-3 left-3 text-[11px] text-zinc-600">
        Drag to pan · scroll to zoom · press 0 to fit
      </p>
    </div>
  );
}

function CanvasButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="pointer-events-auto flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700/70 bg-zinc-900/80 text-zinc-400 backdrop-blur transition hover:border-zinc-600 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
    >
      {children}
    </button>
  );
}
