"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BrainCircuit, PanelRight, X } from "lucide-react";
import type {
  ConnectomeEdgeDto,
  ConnectomeNodeDto,
} from "@/modules/connectome";
import { CommandBar, CommandSettingsLink, type CommandTarget } from "@/components/connectome/command-bar";
import { ConnectomeCanvas } from "@/components/connectome/connectome-canvas";
import { filterBySource } from "@/components/connectome/graph-filter";
import { ConnectomeInspector } from "@/components/connectome/connectome-inspector";
import { ConnectomeTimeline } from "@/components/connectome/connectome-timeline";
import { ContextNav, type SourceFilterItem } from "@/components/connectome/context-nav";
import { nodeStyles } from "@/components/connectome/theme";

/**
 * The five-region workspace: command bar, context navigation, graph, timeline
 * and inspector.
 *
 * Desktop shows all five at once, because the point of the layout is that these
 * are views of one thing. Below 1280px the inspector becomes a slide-over, and
 * below the sidebar breakpoint that becomes a drawer too, so the graph keeps the
 * largest share of a phone screen instead of being squeezed between two panels.
 *
 * The shared focus trap is the one piece worth reading: a drawer that does not
 * manage focus is a drawer keyboard users get stuck behind.
 */

/**
 * Overlay focus management, shared by the navigation and inspector drawers.
 *
 * A drawer that does not move focus is a drawer keyboard users get stranded
 * behind: Tab walks out into the page they cannot see, and Escape does nothing.
 * This pulls focus in, keeps it inside while the overlay is open, locks the
 * page behind it, and hands focus back to the control that opened it.
 */
function useDrawer(
  open: boolean,
  close: () => void,
  panelRef: React.RefObject<HTMLElement | null>,
  toggleRef: React.RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    // Captured now, not in the cleanup, where the ref may already point at a
    // different node.
    const toggle = toggleRef.current;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    const selector =
      "a[href], button:not([disabled]), input, [tabindex]:not([tabindex='-1'])";
    const focusFirst = window.requestAnimationFrame(() => {
      const target = panelRef.current?.querySelector<HTMLElement>(selector);
      (target ?? panelRef.current)?.focus();
    });

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const focusable = [...panelRef.current.querySelectorAll<HTMLElement>(selector)]
        .filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFirst);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      (toggle ?? previouslyFocused)?.focus?.();
    };
  }, [open, close, panelRef, toggleRef]);
}

export interface ConnectomeWorkspaceProps {
  nodes: ConnectomeNodeDto[];
  edges: ConnectomeEdgeDto[];
  sources: SourceFilterItem[];
  developerModeEnabled: boolean;
  initialNodeId: string | null;
  now: string;
}

export function ConnectomeWorkspace({
  nodes,
  edges,
  sources,
  developerModeEnabled,
  initialNodeId,
  now,
}: ConnectomeWorkspaceProps) {
  const [activeSource, setActiveSource] = useState<string | null>(null);
  // `undefined` means "nothing chosen yet", so the node requested in the URL is
  // the selection until the reader picks or clears one. Deriving it here rather
  // than syncing the prop through an effect avoids a second render on load and
  // keeps a cleared selection cleared.
  const [selection, setSelection] = useState<string | null | undefined>(undefined);
  const [frameId, setFrameId] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  const navRef = useRef<HTMLElement>(null);
  const inspectorRef = useRef<HTMLDivElement>(null);
  const navToggleRef = useRef<HTMLButtonElement>(null);
  const inspectorToggleRef = useRef<HTMLButtonElement>(null);

  // Derived once from the server timestamp; reading a ref during render is
  // what the React compiler rules are there to prevent.
  const nowValue = useMemo(() => new Date(now), [now]);

  // Filtering happens here rather than on the server: the whole graph is
  // already loaded, so switching source is instant and cannot leave the map
  // half-rendered while a request is in flight.
  const visible = useMemo(
    () => filterBySource(nodes, edges, activeSource),
    [nodes, edges, activeSource],
  );
  const selectedId = selection === undefined ? initialNodeId : selection;
  const selected = visible.nodes.find((node) => node.id === selectedId) ?? null;

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  useDrawer(navOpen, () => setNavOpen(false), navRef, navToggleRef);
  useDrawer(
    inspectorOpen,
    () => setInspectorOpen(false),
    inspectorRef,
    inspectorToggleRef,
  );

  function select(id: string | null) {
    setSelection(id);
    // Asking to be drawn to a node is what centres the graph on it; clearing
    // the selection releases the view back to the fit.
    setFrameId(id);
    if (id) setInspectorOpen(true);
  }

  const targets: CommandTarget[] = [
    { id: "nav-timeline", label: "Timeline", group: "Go to", href: "/timeline" },
    { id: "nav-dashboard", label: "Overview", group: "Go to", href: "/dashboard" },
    { id: "nav-tasks", label: "Tasks", group: "Go to", href: "/tasks", keywords: "todo" },
    { id: "nav-memory", label: "Memories", group: "Go to", href: "/memory" },
    { id: "nav-people", label: "People", group: "Go to", href: "/people" },
    { id: "nav-connectors", label: "Connectors", group: "Go to", href: "/connectors" },
    { id: "nav-settings", label: "Settings", group: "Go to", href: "/settings" },
  ];

  const counts = useMemo(() => {
    const byKind = new Map<string, number>();
    for (const node of visible.nodes) {
      byKind.set(node.kind, (byKind.get(node.kind) ?? 0) + 1);
    }
    return byKind;
  }, [visible.nodes]);

  const motion = reducedMotion ? "" : "transition-opacity duration-200 motion-reduce:transition-none";

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[#04070f] text-slate-100">
      <a
        href="#connectome-graph"
        className="fixed left-3 top-3 z-[130] -translate-y-20 rounded-lg border border-cyan-300/30 bg-slate-900 px-4 py-2 text-sm font-semibold text-cyan-100 transition focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
      >
        Skip to the graph
      </a>

      <header className="sticky top-0 z-50 flex h-14 shrink-0 items-center gap-3 border-b border-slate-800/70 bg-[#04070f]/92 px-3 backdrop-blur-xl sm:px-4">
        <button
          ref={navToggleRef}
          type="button"
          onClick={() => setNavOpen(true)}
          aria-label="Open context navigation"
          aria-expanded={navOpen}
          aria-controls="connectome-navigation"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-800 text-slate-400 transition hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50 min-[1120px]:hidden"
        >
          <span aria-hidden="true" className="flex flex-col gap-1">
            <span className="block h-px w-4 bg-current" />
            <span className="block h-px w-4 bg-current" />
            <span className="block h-px w-4 bg-current" />
          </span>
        </button>

        <Link
          href="/connectome"
          className="hidden shrink-0 items-center gap-2 rounded-lg pr-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50 sm:flex"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
            <BrainCircuit aria-hidden="true" className="h-3.5 w-3.5" />
          </span>
            <span className="text-[13px] font-semibold tracking-tight text-white">
              Cerebro Flow
            </span>
        </Link>

        <div className="flex min-w-0 flex-1 justify-center">
          <CommandBar nodes={nodes} targets={targets} />
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden text-[11px] tabular-nums text-slate-600 xl:inline">
            {visible.nodes.length} nodes · {visible.edges.length} links
          </span>
          <CommandSettingsLink />
          <button
            ref={inspectorToggleRef}
            type="button"
            onClick={() => setInspectorOpen(true)}
            aria-label="Open intelligence panel"
            aria-expanded={inspectorOpen}
            aria-controls="connectome-inspector"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 text-slate-400 transition hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50 min-[1280px]:hidden"
          >
            <PanelRight aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800/70 bg-[#060a14]/80 min-[1120px]:flex">
          <ContextNav
            sources={sources}
            activeSource={activeSource}
            onSourceChange={setActiveSource}
            developerModeEnabled={developerModeEnabled}
          />
          <div className="shrink-0 border-t border-slate-800/70 px-3 py-2.5">
            <p className="text-[11px] leading-4 text-slate-600">
              Local-first. Every node is an event this device recorded.
            </p>
          </div>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 items-center gap-2 overflow-x-auto border-b border-slate-800/70 px-3 py-2 lg:hidden">
            {[...counts.entries()].map(([kind, count]) => (
              <span
                key={kind}
                className="shrink-0 rounded-full border border-slate-800 px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-slate-500"
              >
                {nodeStyles[kind as keyof typeof nodeStyles]?.short ?? kind} {count}
              </span>
            ))}
          </div>

          <div id="connectome-graph" className="relative min-h-0 flex-1">
            <ConnectomeCanvas
              className="absolute inset-0"
              nodes={visible.nodes}
              edges={visible.edges}
              selectedId={selectedId}
              onSelect={select}
              focusId={frameId}
            />
            {visible.nodes.length === 0 ? (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-6">
                <div className="max-w-sm text-center">
                  <h2 className="text-sm font-semibold text-slate-200">
                    Your brain is still learning.
                  </h2>
                  <p className="mt-1.5 text-xs leading-5 text-slate-500">
                    Connect a source to start building your memory graph. Events
                    appear here the moment they are received.
                  </p>
                </div>
              </div>
            ) : null}
          </div>

          <div className="shrink-0 border-t border-slate-800/70 bg-[#060a14]/60">
            <ConnectomeTimeline
              nodes={visible.nodes}
              selectedId={selectedId}
              onSelect={select}
              now={nowValue}
            />
          </div>
        </main>

        <aside className="hidden w-80 shrink-0 overflow-hidden border-l border-slate-800/70 bg-[#060a14]/80 min-[1280px]:block">
          <ConnectomeInspector
            node={selected}
            nodes={visible.nodes}
            edges={visible.edges}
            now={nowValue}
          />
        </aside>
      </div>

      {navOpen ? (
        <div className="fixed inset-0 z-[110] min-[1120px]:hidden">
          <button
            type="button"
            aria-label="Close navigation overlay"
            onClick={() => setNavOpen(false)}
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
          />
          <aside
            id="connectome-navigation"
            ref={navRef}
            role="dialog"
            aria-modal="true"
            aria-label="Context navigation"
            tabIndex={-1}
            className="absolute inset-y-0 left-0 flex w-[min(17rem,86vw)] flex-col border-r border-slate-800 bg-[#060a14] outline-none"
          >
            <div className="flex h-14 items-center justify-between border-b border-slate-800 px-3">
              <span className="text-[13px] font-semibold text-white">Context</span>
              <button
                type="button"
                onClick={() => setNavOpen(false)}
                aria-label="Close navigation"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                <X aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
            <ContextNav
              sources={sources}
              activeSource={activeSource}
              onSourceChange={(source) => {
                setActiveSource(source);
                setNavOpen(false);
              }}
              developerModeEnabled={developerModeEnabled}
              onNavigate={() => setNavOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      {inspectorOpen ? (
        <div className="fixed inset-0 z-[110] min-[1280px]:hidden">
          <button
            type="button"
            aria-label="Close intelligence panel overlay"
            onClick={() => setInspectorOpen(false)}
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
          />
          <div
            id="connectome-inspector"
            ref={inspectorRef}
            role="dialog"
            aria-modal="true"
            aria-label="Intelligence panel"
            tabIndex={-1}
            className={`absolute inset-y-0 right-0 flex w-[min(22rem,92vw)] flex-col border-l border-slate-800 bg-[#060a14] outline-none ${
              reducedMotion ? "" : "motion-safe:animate-in motion-safe:fade-in"
            }`}
          >
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 px-3">
              <span className="text-[13px] font-semibold text-white">Intelligence</span>
              <button
                type="button"
                onClick={() => setInspectorOpen(false)}
                aria-label="Close intelligence panel"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-800 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50"
              >
                <X aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <ConnectomeInspector
                node={selected}
                nodes={visible.nodes}
                edges={visible.edges}
                now={nowValue}
              />
            </div>
          </div>
        </div>
      ) : null}

      <span className="sr-only" aria-live="polite">
        {selected ? `${nodeStyles[selected.kind].label} ${selected.label} selected` : "Nothing selected"}
      </span>
      <span className={motion} aria-hidden="true" />
    </div>
  );
}
