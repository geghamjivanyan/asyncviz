/**
 * Await-dependency dashboard.
 *
 * Builds a presentation-only surface over the data already streamed
 * into :func:`useAwaitDependencyViews` — no new endpoints, no backend
 * changes, no fabricated metrics. The page composes:
 *
 *   * a summary row (totals + alarm count),
 *   * a topology stats row (depth / fan-out / roots / leaves),
 *   * an interactive SVG graph with pan, zoom, fit-to-screen, filters,
 *     search, and node selection,
 *   * an inspector panel that mirrors the rest of the dashboard's
 *     ``Card`` + ``Badge`` vocabulary.
 *
 * The graph layout is a longest-path layering — O(V+E) — implemented
 * in this file so the page has no new runtime dependencies. Render
 * happens through plain SVG; readable up to a few hundred nodes which
 * is well past the typical await-graph size.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { Card } from "@/ui/primitives/Card";
import { Badge } from "@/ui/primitives/Badge";
import { EmptyState } from "@/ui/feedback/EmptyState";
import type { Intent } from "@/ui/theme/tokens";
import { useAwaitDependencyWebsocketBridge } from "@/dashboard/dependencies/hooks/useAwaitDependencyWebsocketBridge";
import { useAwaitDependencySelection } from "@/dashboard/dependencies/hooks/useAwaitDependencySelection";
import {
  useAwaitDependencyErrorMessage,
  useAwaitDependencyNodeRecords,
  useAwaitDependencyStatus,
  useAwaitDependencyViews,
} from "@/dashboard/dependencies/selectors/AwaitDependencySelectors";
import type {
  AwaitEdgeView,
  AwaitNodeRecord,
  AwaitNodeState,
  AwaitNodeView,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";
import { useTasksById } from "@/state/runtime";
import type { TaskSnapshot } from "@/types/runtime";

// ──────────────────────────────────────────────────────────────────────────
// Page
// ──────────────────────────────────────────────────────────────────────────

export function DependenciesPage(): JSX.Element {
  useAwaitDependencyWebsocketBridge({ enabled: true });

  const { nodes, edges, alarmCount } = useAwaitDependencyViews();
  const nodeRecords = useAwaitDependencyNodeRecords();
  const tasksById = useTasksById();
  const { selectedNodeId, revealNode, selectNode } = useAwaitDependencySelection();
  const status = useAwaitDependencyStatus();
  const errorMessage = useAwaitDependencyErrorMessage();

  const [filters, setFilters] = useState<GraphFilters>(DEFAULT_FILTERS);

  const topology = useMemo(() => buildTopology(nodes, edges), [nodes, edges]);
  const stats = useMemo(
    () => buildStats(nodes, edges, topology, alarmCount),
    [nodes, edges, topology, alarmCount],
  );

  const filtered = useMemo(
    () => applyFilters(nodes, edges, topology, filters),
    [nodes, edges, topology, filters],
  );

  // Cache of previously laid-out node positions. We use it to keep the
  // overall graph centroid stable across re-layouts: when new nodes
  // arrive, the bulk of the visible graph stays put, instead of
  // jittering on every update.
  const prevPositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  const layout = useMemo(() => {
    const raw = layoutDependencyGraph(filtered.nodes, filtered.edges);
    const stabilized = stabilizeLayout(raw, prevPositionsRef.current);
    const next = new Map<string, { x: number; y: number }>();
    for (const n of stabilized.nodes) next.set(n.id, { x: n.x, y: n.y });
    prevPositionsRef.current = next;
    return stabilized;
  }, [filtered]);

  const selectedView = useMemo<AwaitNodeView | null>(
    () => (selectedNodeId === null ? null : (nodes.find((n) => n.id === selectedNodeId) ?? null)),
    [nodes, selectedNodeId],
  );
  const selectedRecord = useMemo<AwaitNodeRecord | null>(
    () =>
      selectedNodeId === null ? null : (nodeRecords.find((r) => r.id === selectedNodeId) ?? null),
    [nodeRecords, selectedNodeId],
  );
  // For task nodes, ``node.id`` IS the task_id — look up the global
  // task snapshot so the inspector can show coroutine name, created /
  // completed times, and the backend-computed duration.
  const selectedTaskSnapshot = useMemo<TaskSnapshot | null>(() => {
    if (selectedNodeId === null) return null;
    if (selectedView?.kind !== "task") return null;
    return tasksById[selectedNodeId] ?? null;
  }, [selectedNodeId, selectedView, tasksById]);

  // Lookup map of every node by id — used by the inspector to render
  // related-node lists (where we want the node's label, not its id).
  const nodesById = useMemo<Map<string, AwaitNodeView>>(() => {
    const m = new Map<string, AwaitNodeView>();
    for (const n of nodes) m.set(n.id, n);
    return m;
  }, [nodes]);

  // Selection counter — bumped every time ``selectedNodeId`` changes so
  // the graph view can replay its node-pulse animation even when the
  // same node is re-clicked.
  const [selectionPulseKey, setSelectionPulseKey] = useState(0);
  const lastSelectedRef = useRef<string | null>(null);
  useEffect(() => {
    if (lastSelectedRef.current === selectedNodeId) return;
    lastSelectedRef.current = selectedNodeId;
    if (selectedNodeId !== null) setSelectionPulseKey((k) => k + 1);
  }, [selectedNodeId]);

  // Navigate to a related node id from the inspector. Looks up the
  // node's kind in the projection so the global runtime ``selectedTaskId``
  // gets synced (via ``revealNode``) for task nodes — the side-effect
  // that lights up the global task inspector on Overview / Timeline.
  const handleNavigate = useCallback(
    (id: string) => {
      const target = nodesById.get(id);
      if (target) revealNode(id, target.kind);
      else selectNode(id);
    },
    [nodesById, revealNode, selectNode],
  );

  // Related-node id buckets for the selected node — computed once and
  // passed to the inspector so the inspector stays presentational.
  const relatedIds = useMemo(() => {
    if (selectedView === null) {
      return {
        parent: null as string | null,
        children: [] as string[],
        incoming: [] as string[],
        outgoing: [] as string[],
      };
    }
    const parent = selectedTaskSnapshot?.parent_task_id ?? selectedView.parentTaskId ?? null;
    const incoming = topology.incoming.get(selectedView.id) ?? [];
    const outgoing = topology.outgoing.get(selectedView.id) ?? [];
    // Children: gather → its fanout edges; task → none in this graph.
    const children =
      selectedView.kind === "gather"
        ? edges
            .filter((e) => e.fromId === selectedView.id && e.kind === "fanout")
            .map((e) => e.toId)
        : [];
    return { parent, children, incoming, outgoing };
  }, [selectedView, selectedTaskSnapshot, topology, edges]);

  const hasNodes = nodes.length > 0;
  const isLoading = status === "loading" && !hasNodes;
  const isError = status === "error";

  return (
    <div
      data-dependencies-page="true"
      className="flex h-full min-h-0 w-full min-w-0 flex-col gap-3 px-4 py-4"
    >
      <header className="flex shrink-0 items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-sm uppercase tracking-widest text-text">Dependencies</h1>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {nodes.length} node{nodes.length === 1 ? "" : "s"} · {edges.length} edge
            {edges.length === 1 ? "" : "s"}
          </span>
        </div>
        {isError && (
          <Badge intent="danger" role="alert">
            {errorMessage ?? "Failed to load dependency graph"}
          </Badge>
        )}
        {isLoading && (
          <Badge intent="accent" aria-live="polite">
            Loading
          </Badge>
        )}
      </header>

      <div className="flex shrink-0 flex-col gap-3">
        <Section title="Dependency summary">
          {hasNodes ? (
            <div
              className="grid gap-2"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(10rem, 1fr))" }}
            >
              <SummaryCell label="Total nodes" value={String(stats.totalNodes)} />
              <SummaryCell label="Total edges" value={String(stats.totalEdges)} />
              <SummaryCell
                label="Active chains"
                value={String(stats.activeChains)}
                intent={stats.activeChains > 0 ? "accent" : "default"}
              />
              <SummaryCell label="Completed chains" value={String(stats.completedChains)} />
              <SummaryCell label="Largest graph" value={String(stats.largestComponent)} />
              <SummaryCell
                label="Dependency alarms"
                value={String(stats.alarmCount)}
                intent={stats.alarmCount > 0 ? "danger" : "default"}
              />
            </div>
          ) : (
            <SectionEmpty />
          )}
        </Section>

        <Section title="Topology">
          {hasNodes ? (
            <div
              className="grid gap-2"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(9rem, 1fr))" }}
            >
              <SummaryCell label="Roots" value={String(stats.rootCount)} />
              <SummaryCell label="Leaves" value={String(stats.leafCount)} />
              <SummaryCell label="Avg depth" value={stats.avgDepth.toFixed(1)} />
              <SummaryCell label="Max depth" value={String(stats.maxDepth)} />
              <SummaryCell label="Avg fan-out" value={stats.avgFanout.toFixed(1)} />
              <SummaryCell label="Max fan-out" value={String(stats.maxFanout)} />
              <SummaryCell
                label="Cycles"
                value={String(stats.cycleCount)}
                intent={stats.cycleCount > 0 ? "warning" : "default"}
              />
            </div>
          ) : (
            <SectionEmpty />
          )}
        </Section>
      </div>

      {hasNodes ? (
        <section className="flex min-h-0 flex-1 flex-col gap-2">
          <h2 className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Dependency graph
          </h2>
          <div className="flex min-h-0 flex-1 gap-2">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <DependencyGraphView
                layout={layout}
                topology={topology}
                selectedNodeId={selectedNodeId}
                selectionPulseKey={selectionPulseKey}
                onSelectNode={(id) => {
                  if (id === null) {
                    selectNode(null);
                    return;
                  }
                  const view = layout.nodes.find((n) => n.id === id);
                  if (view) revealNode(view.id, view.kind);
                }}
                filters={filters}
                onFiltersChange={(next) => setFilters({ ...filters, ...next })}
                totalNodes={nodes.length}
                visibleNodes={layout.nodes.length}
              />
            </div>
            <aside
              aria-label="Dependency inspector"
              className="hidden h-full w-[360px] shrink-0 overflow-y-auto md:flex"
            >
              <DependencyInspector
                view={selectedView}
                record={selectedRecord}
                taskSnapshot={selectedTaskSnapshot}
                topology={topology}
                nodesById={nodesById}
                related={relatedIds}
                onNavigate={handleNavigate}
                onClear={() => selectNode(null)}
              />
            </aside>
          </div>
        </section>
      ) : isLoading ? (
        <SectionEmpty />
      ) : (
        <EmptyState
          title="No await dependencies observed."
          description="Dependency activity appears here as soon as your runtime emits an asyncio.gather event."
        />
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Graph view
// ──────────────────────────────────────────────────────────────────────────

interface DependencyGraphViewProps {
  layout: GraphLayout;
  topology: GraphTopology;
  selectedNodeId: string | null;
  selectionPulseKey: number;
  onSelectNode: (id: string | null) => void;
  filters: GraphFilters;
  onFiltersChange: (patch: Partial<GraphFilters>) => void;
  totalNodes: number;
  visibleNodes: number;
}

interface ViewportTransform {
  panX: number;
  panY: number;
  zoom: number;
}

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 4;
const DEFAULT_TRANSFORM: ViewportTransform = { panX: 0, panY: 0, zoom: 1 };
// Wheel zoom sensitivity. Each notch of a typical mouse wheel produces
// ~3% scale change; trackpad two-finger scrolls (small ``deltaY``)
// land at fractions of a percent. ``ctrlKey + wheel`` is browser-
// standard pinch-to-zoom — give it a slightly stronger response so it
// reads as direct manipulation.
const ZOOM_SENSITIVITY = 0.00035;
const PINCH_SENSITIVITY = 0.006;
// Per-event clamp on the multiplicative factor so a runaway wheel
// (deltaY in the thousands) can't teleport the camera.
const ZOOM_FACTOR_MIN = 0.82;
const ZOOM_FACTOR_MAX = 1.22;
// Below this zoom level node labels are hidden — at < 50% the text
// renders < 5px and overlaps with neighbors, hurting readability more
// than the missing labels do.
const LABEL_HIDE_BELOW_ZOOM = 0.5;
// Smoothing factor for the camera animation. Higher = snappier;
// 0.32 lands roughly between Figma (snappy) and Excalidraw (gentle).
const ZOOM_SMOOTHING = 0.32;

function DependencyGraphView({
  layout,
  topology,
  selectedNodeId,
  selectionPulseKey,
  onSelectNode,
  filters,
  onFiltersChange,
  totalNodes,
  visibleNodes,
}: DependencyGraphViewProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [size, setSize] = useState<{ width: number; height: number }>({
    width: 800,
    height: 480,
  });
  const [transform, setTransform] = useState<ViewportTransform>(DEFAULT_TRANSFORM);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  // Wheel + fit / center / reset go through a rAF-interpolated camera
  // animation; drag and other immediate gestures bypass it. ``target``
  // accumulates desired state so chained wheel events compose instead
  // of fighting an in-flight animation.
  const targetRef = useRef<ViewportTransform>(DEFAULT_TRANSFORM);
  const animFrameRef = useRef<number | null>(null);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    basePanX: number;
    basePanY: number;
    pointerId: number;
    movedPast: boolean;
  } | null>(null);
  const downRef = useRef<{
    x: number;
    y: number;
    onNode: boolean;
  } | null>(null);

  const cancelAnimation = useCallback(() => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  }, []);

  const applyImmediately = useCallback(
    (next: ViewportTransform) => {
      cancelAnimation();
      targetRef.current = next;
      setTransform(next);
    },
    [cancelAnimation],
  );

  const animateTo = useCallback((next: ViewportTransform) => {
    targetRef.current = next;
    if (animFrameRef.current !== null) return;
    const tick = () => {
      setTransform((prev) => {
        const t = targetRef.current;
        const dx = t.panX - prev.panX;
        const dy = t.panY - prev.panY;
        const dz = t.zoom - prev.zoom;
        const close = Math.abs(dx) < 0.4 && Math.abs(dy) < 0.4 && Math.abs(dz) < 0.0008;
        if (close) {
          animFrameRef.current = null;
          return t;
        }
        animFrameRef.current = requestAnimationFrame(tick);
        return {
          panX: prev.panX + dx * ZOOM_SMOOTHING,
          panY: prev.panY + dy * ZOOM_SMOOTHING,
          zoom: prev.zoom + dz * ZOOM_SMOOTHING,
        };
      });
    };
    animFrameRef.current = requestAnimationFrame(tick);
  }, []);

  useEffect(() => () => cancelAnimation(), [cancelAnimation]);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (el === null) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(320, rect.width),
        height: Math.max(280, rect.height),
      });
    };
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const bbox = layout.bbox;

  const fit = useCallback(() => {
    if (bbox.width <= 0 || bbox.height <= 0) {
      animateTo(DEFAULT_TRANSFORM);
      return;
    }
    const padding = 24;
    const scaleX = (size.width - padding * 2) / bbox.width;
    const scaleY = (size.height - padding * 2) / bbox.height;
    const FIT_MAX = 1.8;
    const zoom = Math.max(MIN_ZOOM, Math.min(FIT_MAX, Math.min(scaleX, scaleY)));
    const panX = (size.width - bbox.width * zoom) / 2 - bbox.x * zoom;
    const panY = (size.height - bbox.height * zoom) / 2 - bbox.y * zoom;
    animateTo({ panX, panY, zoom });
  }, [bbox, size, animateTo]);

  const center = useCallback(() => {
    if (bbox.width <= 0) return;
    const cx = bbox.x + bbox.width / 2;
    const cy = bbox.y + bbox.height / 2;
    const cur = targetRef.current;
    animateTo({
      ...cur,
      panX: size.width / 2 - cx * cur.zoom,
      panY: size.height / 2 - cy * cur.zoom,
    });
  }, [bbox, size, animateTo]);

  const reset = useCallback(() => {
    animateTo(DEFAULT_TRANSFORM);
  }, [animateTo]);

  // Auto-fit ONLY on the first appearance of the graph for a given
  // mount; filter changes alter the layout but must preserve the user's
  // current camera. We reset the "has fitted" flag whenever the graph
  // empties out so a freshly-arriving graph re-fits cleanly.
  const hasFittedRef = useRef(false);
  useEffect(() => {
    if (layout.nodes.length === 0) {
      hasFittedRef.current = false;
      return;
    }
    if (hasFittedRef.current) return;
    hasFittedRef.current = true;
    const handle = requestAnimationFrame(fit);
    return () => cancelAnimationFrame(handle);
  }, [layout.nodes.length, fit]);

  // Smoothly center the camera on the selected node — fires on every
  // selection change (graph click OR inspector navigation), keeping the
  // current zoom level. Layout / size changes do not retrigger it
  // because we gate on a ``prevSelected`` ref.
  const prevCenteredRef = useRef<string | null>(null);
  useEffect(() => {
    if (selectedNodeId === null) {
      prevCenteredRef.current = null;
      return;
    }
    if (selectedNodeId === prevCenteredRef.current) return;
    const node = layout.nodes.find((n) => n.id === selectedNodeId);
    if (!node) return; // selected node may be filtered out
    prevCenteredRef.current = selectedNodeId;
    const cur = targetRef.current;
    animateTo({
      zoom: cur.zoom,
      panX: size.width / 2 - node.x * cur.zoom,
      panY: size.height / 2 - node.y * cur.zoom,
    });
  }, [selectedNodeId, layout, size, animateTo]);

  const onWheel = useCallback(
    (event: React.WheelEvent<SVGSVGElement>) => {
      event.preventDefault();
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return;
      const cursorX = event.clientX - rect.left;
      const cursorY = event.clientY - rect.top;
      const sensitivity = event.ctrlKey ? PINCH_SENSITIVITY : ZOOM_SENSITIVITY;
      const rawFactor = Math.exp(-event.deltaY * sensitivity);
      const factor = Math.max(ZOOM_FACTOR_MIN, Math.min(ZOOM_FACTOR_MAX, rawFactor));
      // Use the latest *target* (not the in-flight transform) as the
      // anchor so successive wheel ticks compose into a single smooth
      // animation rather than fighting each other.
      const cur = targetRef.current;
      const nextZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, cur.zoom * factor));
      if (nextZoom === cur.zoom) return;
      const worldX = (cursorX - cur.panX) / cur.zoom;
      const worldY = (cursorY - cur.panY) / cur.zoom;
      animateTo({
        zoom: nextZoom,
        panX: cursorX - worldX * nextZoom,
        panY: cursorY - worldY * nextZoom,
      });
    },
    [animateTo],
  );

  const onPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 && event.button !== 1) return;
    const onNode = (event.target as SVGElement).closest("[data-node-id]") !== null;
    // Track every down so we can distinguish a click on empty canvas
    // (→ clear selection on up) from a click + drag (→ pan only).
    downRef.current = {
      x: event.clientX,
      y: event.clientY,
      onNode,
    };
    // Left button on a node is the node's own click handler; pan only
    // starts when left is on empty canvas, OR when middle button is
    // used anywhere.
    if (event.button === 0 && onNode) return;
    event.preventDefault();
    (event.target as Element).setPointerCapture(event.pointerId);
    // Drag should feel 1:1 — bypass the smoothing animation entirely.
    cancelAnimation();
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      basePanX: transform.panX,
      basePanY: transform.panY,
      pointerId: event.pointerId,
      movedPast: false,
    };
  };
  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (drag === null) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.movedPast && Math.hypot(dx, dy) > 3) {
      drag.movedPast = true;
    }
    applyImmediately({
      ...transform,
      panX: drag.basePanX + dx,
      panY: drag.basePanY + dy,
    });
  };
  const onPointerUp = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    const down = downRef.current;
    dragRef.current = null;
    downRef.current = null;
    try {
      (event.target as Element).releasePointerCapture(event.pointerId);
    } catch {
      /* ignore */
    }
    // Empty-canvas tap (didn't land on a node, didn't drag) clears
    // the current selection — matches the spec's "Selection should
    // remain until another node or empty canvas is clicked".
    if (down !== null && !down.onNode && (drag === null || !drag.movedPast)) {
      const totalDx = event.clientX - down.x;
      const totalDy = event.clientY - down.y;
      if (Math.hypot(totalDx, totalDy) < 4) {
        onSelectNode(null);
      }
    }
  };

  const highlightedIds = useMemo(() => {
    const id = hoveredId ?? selectedNodeId;
    if (id === null) return null;
    return buildNeighborhood(id, layout);
  }, [hoveredId, selectedNodeId, layout]);

  return (
    <Card padding="none" className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
      <GraphToolbar
        filters={filters}
        onFiltersChange={onFiltersChange}
        onFit={fit}
        onCenter={center}
        onReset={reset}
        totalNodes={totalNodes}
        visibleNodes={visibleNodes}
        zoom={transform.zoom}
      />
      <div ref={containerRef} className="relative flex-1 bg-canvas" data-graph-viewport="true">
        {layout.nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
            <p className="font-mono text-xs text-subtle">No nodes match the current filters.</p>
          </div>
        ) : (
          <svg
            ref={svgRef}
            role="img"
            aria-label="Dependency graph"
            width={size.width}
            height={size.height}
            onWheel={onWheel}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            className="block touch-none select-none"
            style={{ cursor: dragRef.current ? "grabbing" : "grab" }}
          >
            <defs>
              {ARROW_INTENTS.map(({ intent, fill }) => (
                <marker
                  key={intent}
                  id={`dep-arrow-${intent}`}
                  viewBox="0 0 10 10"
                  refX="9"
                  refY="5"
                  markerWidth="7"
                  markerHeight="7"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={fill} />
                </marker>
              ))}
            </defs>
            <g
              transform={`translate(${transform.panX} ${transform.panY}) scale(${transform.zoom})`}
            >
              {layout.edges.map((edge) => (
                <EdgeShape
                  key={edge.id}
                  edge={edge}
                  selectedNodeId={selectedNodeId}
                  hoveredId={hoveredId}
                  highlighted={highlightedIds !== null && highlightedIds.edges.has(edge.id)}
                  dim={highlightedIds !== null && !highlightedIds.edges.has(edge.id)}
                />
              ))}
              {layout.nodes.map((node) => (
                <NodeShape
                  key={node.id}
                  node={node}
                  topology={topology}
                  selected={node.id === selectedNodeId}
                  selectionPulseKey={selectionPulseKey}
                  highlighted={highlightedIds !== null && highlightedIds.nodes.has(node.id)}
                  dim={highlightedIds !== null && !highlightedIds.nodes.has(node.id)}
                  showLabel={transform.zoom >= LABEL_HIDE_BELOW_ZOOM}
                  onHover={setHoveredId}
                  onSelect={onSelectNode}
                />
              ))}
            </g>
          </svg>
        )}
      </div>
    </Card>
  );
}

// ── graph toolbar ─────────────────────────────────────────────────────────

interface GraphToolbarProps {
  filters: GraphFilters;
  onFiltersChange: (patch: Partial<GraphFilters>) => void;
  onFit: () => void;
  onCenter: () => void;
  onReset: () => void;
  totalNodes: number;
  visibleNodes: number;
  zoom: number;
}

function GraphToolbar({
  filters,
  onFiltersChange,
  onFit,
  onCenter,
  onReset,
  totalNodes,
  visibleNodes,
  zoom,
}: GraphToolbarProps): JSX.Element {
  return (
    <div
      role="toolbar"
      aria-label="Dependency graph controls"
      className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-3 py-2 text-xs"
    >
      <ToolButton onClick={onFit} title="Fit graph to viewport" label="Fit" />
      <ToolButton onClick={onCenter} title="Center graph in viewport" label="Center" />
      <ToolButton onClick={onReset} title="Reset zoom + pan" label="Reset" />
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
        {Math.round(zoom * 100)}%
      </span>
      <div className="mx-1 h-4 w-px bg-line" aria-hidden="true" />
      <ToolToggle
        active={filters.activeOnly}
        onClick={() => onFiltersChange({ activeOnly: !filters.activeOnly })}
        label="Active only"
        title="Show only running or pending nodes"
      />
      <ToolToggle
        active={filters.hideCompleted}
        onClick={() => onFiltersChange({ hideCompleted: !filters.hideCompleted })}
        label="Hide completed"
        title="Hide nodes whose state is completed"
      />
      <ToolToggle
        active={filters.hideTerminal}
        onClick={() => onFiltersChange({ hideTerminal: !filters.hideTerminal })}
        label="Hide finished"
        title="Hide completed, cancelled, and failed nodes"
      />
      <ToolToggle
        active={filters.collapseCompleted}
        onClick={() => onFiltersChange({ collapseCompleted: !filters.collapseCompleted })}
        label="Collapse completed"
        title="Hide descendants of completed gather nodes"
      />
      <label className="ml-auto flex items-center gap-2 text-subtle">
        <span className="text-[10px] uppercase tracking-widest text-muted">Search</span>
        <input
          type="search"
          value={filters.search}
          onChange={(e) => onFiltersChange({ search: e.target.value })}
          placeholder="Filter by label or id…"
          aria-label="Search nodes"
          className="w-40 rounded border border-line bg-canvas px-2 py-0.5 font-mono text-xs text-text outline-none placeholder:text-subtle focus:border-accent"
        />
      </label>
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
        {visibleNodes}/{totalNodes} visible
      </span>
    </div>
  );
}

function ToolButton({
  onClick,
  title,
  label,
}: {
  onClick: () => void;
  title: string;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="rounded border border-line bg-canvas px-2 py-0.5 font-mono text-xs uppercase tracking-widest text-text hover:border-accent hover:text-accent"
    >
      {label}
    </button>
  );
}

function ToolToggle({
  active,
  onClick,
  label,
  title,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  title: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={active}
      className={cn(
        "rounded border px-2 py-0.5 font-mono text-xs uppercase tracking-widest",
        active
          ? "border-accent text-accent"
          : "border-line text-subtle hover:border-accent hover:text-accent",
      )}
    >
      {label}
    </button>
  );
}

// ── SVG primitives ───────────────────────────────────────────────────────

const NODE_SIZE = 22;
const GATHER_SIZE = 30;

const STATE_FILL: Record<AwaitNodeState, string> = {
  pending: "var(--color-subtle, #4f545e)",
  running: "var(--color-success, #22d36b)",
  completed: "var(--color-muted, #5f6470)",
  cancelled: "var(--color-warning, #facc15)",
  failed: "var(--color-danger, #fb6a6a)",
};

const STATE_STROKE: Record<AwaitNodeState, string> = {
  pending: "var(--color-muted, #5f6470)",
  running: "var(--color-success, #22d36b)",
  completed: "var(--color-line, #1f2430)",
  cancelled: "var(--color-warning, #facc15)",
  failed: "var(--color-danger, #fb6a6a)",
};

const STATE_TEXT: Record<AwaitNodeState, string> = {
  pending: "text-muted",
  running: "text-success",
  completed: "text-muted",
  cancelled: "text-warning",
  failed: "text-danger",
};

const ARROW_INTENTS = [
  { intent: "default", fill: "var(--color-line, #1f2430)" },
  { intent: "accent", fill: "var(--color-accent, #60a5fa)" },
  { intent: "warning", fill: "var(--color-warning, #facc15)" },
  { intent: "danger", fill: "var(--color-danger, #fb6a6a)" },
  { intent: "muted", fill: "var(--color-muted, #5f6470)" },
] as const;

type ArrowIntent = (typeof ARROW_INTENTS)[number]["intent"];

function edgeIntent(edge: LaidOutEdge): ArrowIntent {
  if (edge.failed) return "danger";
  if (edge.cancelled) return "warning";
  if (edge.kind === "fanout") return "accent";
  if (edge.completed) return "muted";
  return "default";
}

function NodeShape({
  node,
  topology,
  selected,
  selectionPulseKey,
  highlighted,
  dim,
  showLabel,
  onHover,
  onSelect,
}: {
  node: LaidOutNode;
  topology: GraphTopology;
  selected: boolean;
  selectionPulseKey: number;
  highlighted: boolean;
  dim: boolean;
  showLabel: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
}): JSX.Element {
  const fill = STATE_FILL[node.state];
  const stroke = selected
    ? "var(--color-accent, #60a5fa)"
    : highlighted
      ? "var(--color-accent, #60a5fa)"
      : STATE_STROKE[node.state];
  const strokeWidth = selected ? 2.5 : node.isRoot ? 2 : 1.25;
  const opacity = dim ? 0.25 : 1;
  const isGather = node.kind === "gather";
  const isLeaf = (topology.outDegree.get(node.id) ?? 0) === 0;
  const label = truncate(node.label, 14);

  return (
    <g
      data-node-id={node.id}
      data-node-kind={node.kind}
      data-node-state={node.state}
      transform={`translate(${node.x} ${node.y})`}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(selected ? null : node.id);
      }}
      style={{ cursor: "pointer", opacity }}
    >
      {isGather ? (
        <rect
          x={-GATHER_SIZE / 2}
          y={-GATHER_SIZE / 2}
          width={GATHER_SIZE}
          height={GATHER_SIZE}
          rx={6}
          ry={6}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          strokeDasharray={isLeaf ? "3 3" : undefined}
        />
      ) : (
        <circle
          r={NODE_SIZE / 2}
          fill={fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          strokeDasharray={isLeaf ? "3 3" : undefined}
        />
      )}
      {node.isRoot && (
        <circle
          r={(isGather ? GATHER_SIZE : NODE_SIZE) / 2 + 4}
          fill="none"
          stroke={stroke}
          strokeOpacity={0.5}
          strokeWidth={1}
        />
      )}
      {/* One-shot pulse ring on every fresh selection. Keyed on the
          page-level pulse counter so re-selecting the same node
          replays the animation. */}
      {selected && (
        <circle
          key={`pulse-${selectionPulseKey}`}
          r={(isGather ? GATHER_SIZE : NODE_SIZE) / 2 + 2}
          fill="none"
          stroke="var(--color-accent, #60a5fa)"
          strokeWidth={2}
          pointerEvents="none"
        >
          <animate
            attributeName="r"
            from={(isGather ? GATHER_SIZE : NODE_SIZE) / 2 + 2}
            to={(isGather ? GATHER_SIZE : NODE_SIZE) / 2 + 22}
            dur="0.8s"
            begin="0s"
            fill="freeze"
          />
          <animate
            attributeName="stroke-opacity"
            from={0.85}
            to={0}
            dur="0.8s"
            begin="0s"
            fill="freeze"
          />
        </circle>
      )}
      {/* Native SVG tooltip: hovering the node reveals the full id /
          label without any extra overlay. */}
      <title>{node.label}</title>
      {showLabel && (
        <text
          x={0}
          y={(isGather ? GATHER_SIZE : NODE_SIZE) / 2 + 14}
          textAnchor="middle"
          className={cn("pointer-events-none font-mono text-[10px]", STATE_TEXT[node.state])}
          fill="currentColor"
        >
          {label}
        </text>
      )}
    </g>
  );
}

function EdgeShape({
  edge,
  selectedNodeId,
  hoveredId,
  highlighted,
  dim,
}: {
  edge: LaidOutEdge;
  selectedNodeId: string | null;
  hoveredId: string | null;
  highlighted: boolean;
  dim: boolean;
}): JSX.Element {
  const intent = edgeIntent(edge);
  const fillVar = ARROW_INTENTS.find((a) => a.intent === intent)?.fill ?? ARROW_INTENTS[0].fill;
  const baseOpacity = edge.completed ? 0.45 : 0.85;
  const opacity = dim ? 0.08 : highlighted ? 1 : baseOpacity;
  const touches =
    selectedNodeId !== null && (edge.fromId === selectedNodeId || edge.toId === selectedNodeId);
  const hovered = hoveredId !== null && (edge.fromId === hoveredId || edge.toId === hoveredId);
  const strokeWidth = touches || hovered ? 2 : 1.25;
  const dash = edge.kind === "fanout" ? undefined : edge.completed ? "4 3" : undefined;
  // Top-down layout: bend along the y-axis so edges read as smooth
  // vertical S-curves rather than horizontal zig-zags.
  const dy = (edge.toY - edge.fromY) / 2;
  const path = `M ${edge.fromX} ${edge.fromY} C ${edge.fromX} ${edge.fromY + dy}, ${edge.toX} ${edge.toY - dy}, ${edge.toX} ${edge.toY}`;
  return (
    <path
      data-edge-id={edge.id}
      d={path}
      fill="none"
      stroke={fillVar}
      strokeWidth={strokeWidth}
      strokeOpacity={opacity}
      strokeLinecap="round"
      strokeDasharray={dash}
      markerEnd={`url(#dep-arrow-${intent})`}
    />
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Inspector
// ──────────────────────────────────────────────────────────────────────────

interface RelatedIds {
  parent: string | null;
  children: string[];
  incoming: string[];
  outgoing: string[];
}

function DependencyInspector({
  view,
  record,
  taskSnapshot,
  topology,
  nodesById,
  related,
  onNavigate,
  onClear,
}: {
  view: AwaitNodeView | null;
  record: AwaitNodeRecord | null;
  taskSnapshot: TaskSnapshot | null;
  topology: GraphTopology;
  nodesById: Map<string, AwaitNodeView>;
  related: RelatedIds;
  onNavigate: (id: string) => void;
  onClear: () => void;
}): JSX.Element {
  if (view === null) {
    return (
      <Card padding="md" className="flex h-full w-full flex-col gap-3">
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Inspector
        </span>
        <p className="font-mono text-xs leading-relaxed text-subtle">
          Click a node in the graph to inspect its dependencies, state, and timing.
        </p>
      </Card>
    );
  }

  const stateIntent = NODE_STATE_INTENT[view.state];
  const inDegree = topology.inDegree.get(view.id) ?? 0;
  const outDegree = topology.outDegree.get(view.id) ?? 0;
  const dependencyCount = inDegree + outDegree;

  const coroutine =
    taskSnapshot?.coroutine_name ??
    (view.kind === "task" && view.label !== view.id ? view.label : null);

  const createdSeconds = taskSnapshot?.created_at ?? null;
  const completedSeconds = taskSnapshot?.completed_at ?? null;
  const durationFromTask = taskSnapshot?.duration_seconds ?? null;
  const startedSeconds =
    completedSeconds !== null && durationFromTask !== null
      ? completedSeconds - durationFromTask
      : null;

  const duration =
    durationFromTask !== null
      ? durationFromTask
      : view.durationSeconds !== null
        ? view.durationSeconds
        : null;

  // Snapshot "now" once per render so the relative-time strings are
  // consistent across all timing rows.
  const nowSeconds = Date.now() / 1000;

  return (
    <Card padding="md" className="flex h-full w-full flex-col gap-4">
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Inspector
          </span>
          <span className="truncate font-mono text-sm text-text" title={view.label}>
            {view.label}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">
            {view.kind === "gather" ? "Gather" : "Task"}
          </span>
        </div>
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear selection"
          title="Clear selection"
          className="shrink-0 rounded border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-subtle hover:border-accent hover:text-accent"
        >
          Clear selection
        </button>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Badge intent={stateIntent}>{view.state.toUpperCase()}</Badge>
        {view.kind === "gather" && view.exceptionType !== null && (
          <Badge intent="danger">{view.exceptionType}</Badge>
        )}
      </div>

      <Field label="Task id" value={view.id} mono />
      <Field label="Coroutine" value={coroutine ?? "—"} mono={coroutine !== null} />

      <Section2 title="Relationships">
        <KV label="Depth" value={String(topology.layer.get(view.id) ?? 0)} />
        <KV
          label="Dependencies"
          value={String(dependencyCount)}
          intent={dependencyCount > 0 ? "accent" : undefined}
        />
        <RelatedRow
          label="Parent"
          ids={related.parent !== null ? [related.parent] : []}
          nodesById={nodesById}
          onNavigate={onNavigate}
        />
        <RelatedRow
          label="Children"
          ids={view.kind === "gather" ? related.children : []}
          nodesById={nodesById}
          onNavigate={onNavigate}
          totalOverride={view.kind === "gather" ? view.childCount : undefined}
        />
        <RelatedRow
          label="Incoming"
          ids={related.incoming}
          nodesById={nodesById}
          onNavigate={onNavigate}
        />
        <RelatedRow
          label="Outgoing"
          ids={related.outgoing}
          nodesById={nodesById}
          onNavigate={onNavigate}
        />
      </Section2>

      {view.kind === "gather" && (
        <Section2 title="Progress">
          <KV
            label="Progress"
            value={`${Math.round(view.progressRatio * 100)}%`}
            intent={view.progressRatio >= 1 ? "default" : "accent"}
          />
          <KV label="Completed" value={`${view.completedCount} / ${view.childCount}`} />
          <KV
            label="Cancelled"
            value={String(view.cancelledCount)}
            intent={view.cancelledCount > 0 ? "warning" : undefined}
          />
          <KV
            label="Failed"
            value={String(view.failedCount)}
            intent={view.failedCount > 0 ? "danger" : undefined}
          />
        </Section2>
      )}

      <Section2 title="Timing">
        <TimeRow label="Created" wallSeconds={createdSeconds} nowSeconds={nowSeconds} />
        <TimeRow label="Started" wallSeconds={startedSeconds} nowSeconds={nowSeconds} />
        <TimeRow label="Completed" wallSeconds={completedSeconds} nowSeconds={nowSeconds} />
        <KV label="Duration" value={duration !== null ? formatDurationFriendly(duration) : "—"} />
        {record !== null && record.firstSeenNs > 0 && (
          <KV label="First observed" value={formatDurationFriendly(record.firstSeenNs / 1e9)} />
        )}
        {record !== null && record.lastSeenNs > 0 && (
          <KV label="Last observed" value={formatDurationFriendly(record.lastSeenNs / 1e9)} />
        )}
      </Section2>
    </Card>
  );
}

// ── Inspector building blocks ────────────────────────────────────────────

function RelatedRow({
  label,
  ids,
  nodesById,
  onNavigate,
  totalOverride,
}: {
  label: string;
  ids: readonly string[];
  nodesById: Map<string, AwaitNodeView>;
  onNavigate: (id: string) => void;
  totalOverride?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const PREVIEW = 3;
  const count = totalOverride ?? ids.length;
  if (count === 0 || ids.length === 0) {
    return (
      <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
        <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
        <span className="text-subtle">—</span>
      </div>
    );
  }
  const visible = expanded ? ids : ids.slice(0, PREVIEW);
  const hasMore = ids.length > PREVIEW;
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => hasMore && setExpanded((v) => !v)}
        className={cn(
          "flex items-baseline justify-between gap-3 font-mono text-xs",
          hasMore ? "cursor-pointer hover:text-accent" : "cursor-default",
        )}
        aria-expanded={expanded}
        title={hasMore ? "Expand" : undefined}
      >
        <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
        <span className="flex items-baseline gap-1 text-text">
          <span className="tabular-nums">{count}</span>
          {hasMore && (
            <span aria-hidden="true" className="text-[10px] text-subtle">
              {expanded ? "▾" : "▸"}
            </span>
          )}
        </span>
      </button>
      <ul className="flex flex-col gap-0.5 pl-2">
        {visible.map((id) => {
          const node = nodesById.get(id);
          const display = node?.label ?? id;
          const kindLabel =
            node?.kind === "gather" ? "gather" : node?.kind === "task" ? "task" : "?";
          return (
            <li key={id}>
              <button
                type="button"
                onClick={() => onNavigate(id)}
                title={id}
                className="flex w-full items-baseline justify-between gap-2 text-left font-mono text-[11px] text-muted hover:text-accent"
              >
                <span className="truncate">{display}</span>
                <span className="shrink-0 text-[10px] uppercase tracking-widest text-subtle">
                  {kindLabel}
                </span>
              </button>
            </li>
          );
        })}
        {!expanded && hasMore && (
          <li className="font-mono text-[11px] text-subtle">+{ids.length - PREVIEW} more</li>
        )}
      </ul>
    </div>
  );
}

function TimeRow({
  label,
  wallSeconds,
  nowSeconds,
}: {
  label: string;
  wallSeconds: number | null;
  nowSeconds: number;
}) {
  if (wallSeconds === null || !Number.isFinite(wallSeconds) || wallSeconds <= 0) {
    return (
      <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
        <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
        <span className="text-subtle">—</span>
      </div>
    );
  }
  return (
    <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className="flex flex-col items-end gap-0">
        <span className="tabular-nums text-text">{formatWallSeconds(wallSeconds)}</span>
        <span className="text-[10px] uppercase tracking-widest text-subtle">
          {formatRelativeFromNow(wallSeconds, nowSeconds)}
        </span>
      </span>
    </div>
  );
}

// μs / ms / s / min / h — picks the most appropriate unit for the value.
function formatDurationFriendly(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds === 0) return "0s";
  if (seconds < 1e-3) return `${(seconds * 1e6).toFixed(0)}μs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return `${minutes}min ${rest.toString().padStart(2, "0")}s`;
  }
  const hours = Math.floor(seconds / 3600);
  const remMin = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${remMin.toString().padStart(2, "0")}min`;
}

function formatRelativeFromNow(wallSeconds: number, nowSeconds: number): string {
  const delta = nowSeconds - wallSeconds;
  if (!Number.isFinite(delta)) return "—";
  if (delta < 0) return `in ${formatDurationFriendly(-delta)}`;
  if (delta < 1) return "just now";
  return `${formatDurationFriendly(delta)} ago`;
}

function formatWallSeconds(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 1e6) return formatSeconds(seconds);
  try {
    const d = new Date(seconds * 1000);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toISOString().slice(11, 23);
  } catch {
    return "—";
  }
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className={cn("text-xs text-text", mono ? "break-all font-mono" : "")}>{value}</span>
    </div>
  );
}

function Section2({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5 border-t border-line/40 pt-2">
      <span className="font-mono text-[10px] uppercase tracking-widest text-subtle">{title}</span>
      <div className="flex flex-col gap-1">{children}</div>
    </section>
  );
}

function KV({ label, value, intent }: { label: string; value: string; intent?: Intent }) {
  const valueColor =
    intent === "danger"
      ? "text-danger"
      : intent === "warning"
        ? "text-warning"
        : intent === "success"
          ? "text-success"
          : intent === "accent"
            ? "text-accent"
            : "text-text";
  return (
    <div className="flex items-baseline justify-between gap-3 font-mono text-xs">
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className={cn("tabular-nums", valueColor)}>{value}</span>
    </div>
  );
}

const NODE_STATE_INTENT: Record<AwaitNodeState, Intent> = {
  pending: "default",
  running: "success",
  completed: "default",
  cancelled: "warning",
  failed: "danger",
};

// ──────────────────────────────────────────────────────────────────────────
// Filters + topology + layout + stats
// ──────────────────────────────────────────────────────────────────────────

interface GraphFilters {
  search: string;
  activeOnly: boolean;
  hideCompleted: boolean;
  hideTerminal: boolean;
  collapseCompleted: boolean;
}

const DEFAULT_FILTERS: GraphFilters = {
  search: "",
  activeOnly: false,
  hideCompleted: false,
  hideTerminal: false,
  collapseCompleted: false,
};

interface GraphTopology {
  outgoing: Map<string, string[]>;
  incoming: Map<string, string[]>;
  outDegree: Map<string, number>;
  inDegree: Map<string, number>;
  layer: Map<string, number>;
  componentId: Map<string, number>;
  componentSizes: number[];
  cycleCount: number;
}

function buildTopology(
  nodes: readonly AwaitNodeView[],
  edges: readonly AwaitEdgeView[],
): GraphTopology {
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();
  for (const node of nodes) {
    outgoing.set(node.id, []);
    incoming.set(node.id, []);
  }
  for (const edge of edges) {
    if (!outgoing.has(edge.fromId) || !incoming.has(edge.toId)) continue;
    outgoing.get(edge.fromId)!.push(edge.toId);
    incoming.get(edge.toId)!.push(edge.fromId);
  }
  const outDegree = new Map<string, number>();
  const inDegree = new Map<string, number>();
  for (const [id, list] of outgoing) outDegree.set(id, list.length);
  for (const [id, list] of incoming) inDegree.set(id, list.length);

  const layer = new Map<string, number>();
  const remaining = new Map<string, number>(inDegree);
  const queue: string[] = [];
  for (const [id, deg] of remaining) {
    if (deg === 0) {
      queue.push(id);
      layer.set(id, 0);
    }
  }
  let visited = 0;
  while (queue.length > 0) {
    const id = queue.shift()!;
    visited += 1;
    const myLayer = layer.get(id) ?? 0;
    for (const nextId of outgoing.get(id) ?? []) {
      const proposed = myLayer + 1;
      if ((layer.get(nextId) ?? -1) < proposed) layer.set(nextId, proposed);
      remaining.set(nextId, (remaining.get(nextId) ?? 0) - 1);
      if (remaining.get(nextId) === 0) queue.push(nextId);
    }
  }
  for (const node of nodes) {
    if (!layer.has(node.id)) layer.set(node.id, 0);
  }
  const cycleCount = nodes.length - visited;

  const componentId = new Map<string, number>();
  const componentSizes: number[] = [];
  for (const node of nodes) {
    if (componentId.has(node.id)) continue;
    const idx = componentSizes.length;
    componentSizes.push(0);
    const stack = [node.id];
    while (stack.length > 0) {
      const cur = stack.pop()!;
      if (componentId.has(cur)) continue;
      componentId.set(cur, idx);
      componentSizes[idx] += 1;
      for (const next of outgoing.get(cur) ?? []) stack.push(next);
      for (const prev of incoming.get(cur) ?? []) stack.push(prev);
    }
  }

  return {
    outgoing,
    incoming,
    outDegree,
    inDegree,
    layer,
    componentId,
    componentSizes,
    cycleCount,
  };
}

interface GraphStats {
  totalNodes: number;
  totalEdges: number;
  activeChains: number;
  completedChains: number;
  largestComponent: number;
  alarmCount: number;
  rootCount: number;
  leafCount: number;
  avgDepth: number;
  maxDepth: number;
  avgFanout: number;
  maxFanout: number;
  cycleCount: number;
}

function buildStats(
  nodes: readonly AwaitNodeView[],
  edges: readonly AwaitEdgeView[],
  topology: GraphTopology,
  alarmCount: number,
): GraphStats {
  let activeChains = 0;
  let completedChains = 0;
  let rootCount = 0;
  let leafCount = 0;
  let depthSum = 0;
  let maxDepth = 0;
  let fanoutSum = 0;
  let fanoutCount = 0;
  let maxFanout = 0;
  for (const node of nodes) {
    if (node.kind === "gather") {
      if (node.state === "running" || node.state === "pending") activeChains += 1;
      else if (node.state === "completed") completedChains += 1;
    }
    const inDeg = topology.inDegree.get(node.id) ?? 0;
    const outDeg = topology.outDegree.get(node.id) ?? 0;
    if (inDeg === 0) rootCount += 1;
    if (outDeg === 0) leafCount += 1;
    const layer = topology.layer.get(node.id) ?? 0;
    depthSum += layer;
    if (layer > maxDepth) maxDepth = layer;
    if (outDeg > 0) {
      fanoutSum += outDeg;
      fanoutCount += 1;
      if (outDeg > maxFanout) maxFanout = outDeg;
    }
  }
  const largestComponent = topology.componentSizes.reduce((a, b) => (b > a ? b : a), 0);
  return {
    totalNodes: nodes.length,
    totalEdges: edges.length,
    activeChains,
    completedChains,
    largestComponent,
    alarmCount,
    rootCount,
    leafCount,
    avgDepth: nodes.length > 0 ? depthSum / nodes.length : 0,
    maxDepth,
    avgFanout: fanoutCount > 0 ? fanoutSum / fanoutCount : 0,
    maxFanout,
    cycleCount: topology.cycleCount,
  };
}

function applyFilters(
  nodes: readonly AwaitNodeView[],
  edges: readonly AwaitEdgeView[],
  topology: GraphTopology,
  filters: GraphFilters,
): { nodes: AwaitNodeView[]; edges: AwaitEdgeView[] } {
  const visible = new Set<string>(nodes.map((n) => n.id));
  const term = filters.search.trim().toLowerCase();

  if (filters.activeOnly) {
    for (const node of nodes) {
      if (node.state !== "running" && node.state !== "pending") visible.delete(node.id);
    }
  }
  if (filters.hideCompleted) {
    for (const node of nodes) if (node.state === "completed") visible.delete(node.id);
  }
  if (filters.hideTerminal) {
    for (const node of nodes) {
      if (node.state === "completed" || node.state === "cancelled" || node.state === "failed")
        visible.delete(node.id);
    }
  }
  if (filters.collapseCompleted) {
    const queue: string[] = [];
    for (const node of nodes) {
      if (node.kind === "gather" && node.state === "completed") queue.push(node.id);
    }
    const seen = new Set<string>(queue);
    while (queue.length > 0) {
      const id = queue.shift()!;
      for (const next of topology.outgoing.get(id) ?? []) {
        if (seen.has(next)) continue;
        seen.add(next);
        visible.delete(next);
        queue.push(next);
      }
    }
  }
  if (term.length > 0) {
    const matched = new Set<string>();
    for (const node of nodes) {
      if (node.label.toLowerCase().includes(term) || node.id.toLowerCase().includes(term)) {
        matched.add(node.id);
      }
    }
    const keep = new Set<string>(matched);
    for (const id of matched) {
      for (const o of topology.outgoing.get(id) ?? []) keep.add(o);
      for (const i of topology.incoming.get(id) ?? []) keep.add(i);
    }
    for (const id of Array.from(visible)) {
      if (!keep.has(id)) visible.delete(id);
    }
  }

  const filteredNodes = nodes.filter((n) => visible.has(n.id));
  const filteredEdges = edges.filter((e) => visible.has(e.fromId) && visible.has(e.toId));
  return { nodes: filteredNodes, edges: filteredEdges };
}

// ── Layout ───────────────────────────────────────────────────────────────

interface LaidOutNode {
  id: string;
  kind: AwaitNodeView["kind"];
  state: AwaitNodeState;
  label: string;
  x: number;
  y: number;
  isRoot: boolean;
}

interface LaidOutEdge {
  id: string;
  fromId: string;
  toId: string;
  kind: AwaitEdgeView["kind"];
  completed: boolean;
  cancelled: boolean;
  failed: boolean;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
}

interface GraphLayout {
  nodes: LaidOutNode[];
  edges: LaidOutEdge[];
  bbox: { x: number; y: number; width: number; height: number };
}

// ── Layout constants ────────────────────────────────────────────────────
//
// Orientation: layers stack TOP → BOTTOM (y axis) and siblings within
// a layer spread LEFT → RIGHT (x axis). A broad gather with 100 children
// becomes a wide row below the gather instead of a 100-deep column.

const LAYER_SPACING = 120; // vertical gap between layers
const NODE_SPACING = 150; // horizontal gap between sibling nodes
const COMPONENT_GAP_X = 140; // horizontal gap between independent trees
const COMPONENT_GAP_Y = 90; // vertical gap when a row of components wraps
const BARYCENTER_SWEEPS = 6;
// A single layer wider than this gets wrapped into sub-rows so one
// huge fan-out gather doesn't flatten the entire layout into one strip.
const MAX_LAYER_WIDTH = 1400;
const SUB_ROW_SPACING = 72;
// Overall packing aspect ratio (width : height). Slightly wide because
// most monitors are landscape — the layout still fits a portrait area
// comfortably, this just nudges the natural shape.
const TARGET_ASPECT = 1.3;

interface ComponentBlock {
  nodes: LaidOutNode[];
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  width: number;
  height: number;
}

function layoutDependencyGraph(
  nodes: readonly AwaitNodeView[],
  edges: readonly AwaitEdgeView[],
): GraphLayout {
  if (nodes.length === 0) {
    return { nodes: [], edges: [], bbox: { x: 0, y: 0, width: 0, height: 0 } };
  }
  const topology = buildTopology(nodes, edges);

  // Group nodes by connected component. Disjoint dependency trees
  // get their own block and are packed side-by-side later so unrelated
  // graphs never share the same column.
  const componentMembers = new Map<number, AwaitNodeView[]>();
  for (const node of nodes) {
    const cid = topology.componentId.get(node.id) ?? 0;
    const bucket = componentMembers.get(cid) ?? [];
    bucket.push(node);
    componentMembers.set(cid, bucket);
  }

  // Lay out each component independently with a layered top-down layout.
  const blocks: ComponentBlock[] = [];
  for (const members of componentMembers.values()) {
    blocks.push(layoutComponentBlock(members, edges, topology));
  }
  // Largest components first so they anchor each row; small fragments
  // tuck into the trailing space without forcing a wrap. Ties break on
  // the lowest member id so repeated layouts of the same data produce
  // the same packing (stability across live updates).
  blocks.sort((a, b) => {
    if (a.nodes.length !== b.nodes.length) return b.nodes.length - a.nodes.length;
    const aId = a.nodes[0]?.id ?? "";
    const bId = b.nodes[0]?.id ?? "";
    return aId.localeCompare(bId);
  });

  // Each block effectively occupies a cell at least
  // ``NODE_SPACING × LAYER_SPACING`` (so a single-node component still
  // contributes meaningful packing area, not just its zero-width bbox).
  // The target row width is derived from the SUM of cell areas — wider
  // when there's more content, narrower when there's less, balanced
  // against the desired aspect ratio.
  let totalCellArea = 0;
  for (const block of blocks) {
    const w = Math.max(block.width, NODE_SPACING) + COMPONENT_GAP_X;
    const h = Math.max(block.height, LAYER_SPACING) + COMPONENT_GAP_Y;
    totalCellArea += w * h;
  }
  const minRowWidth = NODE_SPACING * 4;
  const targetRowWidth = Math.max(minRowWidth, Math.sqrt(totalCellArea * TARGET_ASPECT));

  const positions = new Map<string, { x: number; y: number }>();
  const laidOut: LaidOutNode[] = [];
  let rowOffsetY = 0;
  let rowCursorX = 0;
  let rowHeight = 0;
  for (const block of blocks) {
    // Each block reserves a cell with a horizontal floor of
    // ``NODE_SPACING`` so a 1-node component still occupies a slot wide
    // enough to host its label — matching the area-based row width.
    const effectiveW = Math.max(block.width, NODE_SPACING);
    if (rowCursorX > 0 && rowCursorX + effectiveW > targetRowWidth) {
      rowOffsetY += rowHeight + COMPONENT_GAP_Y;
      rowCursorX = 0;
      rowHeight = 0;
    }
    // Center the component inside its (potentially wider) cell.
    const centerOffset = (effectiveW - block.width) / 2;
    const dx = rowCursorX + centerOffset - block.minX;
    const dy = rowOffsetY - block.minY;
    for (const node of block.nodes) {
      const x = node.x + dx;
      const y = node.y + dy;
      positions.set(node.id, { x, y });
      laidOut.push({ ...node, x, y });
    }
    rowCursorX += effectiveW + COMPONENT_GAP_X;
    if (block.height > rowHeight) rowHeight = block.height;
  }

  // Edges resolve their endpoints from the final, global positions.
  const laidOutEdges: LaidOutEdge[] = [];
  for (const edge of edges) {
    const from = positions.get(edge.fromId);
    const to = positions.get(edge.toId);
    if (from === undefined || to === undefined) continue;
    laidOutEdges.push({
      id: edge.id,
      fromId: edge.fromId,
      toId: edge.toId,
      kind: edge.kind,
      completed: edge.completed,
      cancelled: edge.cancelled,
      failed: edge.failed,
      fromX: from.x,
      fromY: from.y,
      toX: to.x,
      toY: to.y,
    });
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const n of laidOut) {
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x > maxX) maxX = n.x;
    if (n.y > maxY) maxY = n.y;
  }
  const pad = 60;
  const bbox = {
    x: minX - pad,
    y: minY - pad,
    width: maxX - minX + pad * 2,
    height: maxY - minY + pad * 2,
  };
  return { nodes: laidOut, edges: laidOutEdges, bbox };
}

// Per-component layered (top-down) layout with barycenter ordering.
function layoutComponentBlock(
  members: readonly AwaitNodeView[],
  allEdges: readonly AwaitEdgeView[],
  topology: GraphTopology,
): ComponentBlock {
  const memberIds = new Set(members.map((n) => n.id));
  // Component-local adjacency: keeps barycenter math from accidentally
  // dragging in nodes that belong to a different tree.
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();
  for (const node of members) {
    outgoing.set(node.id, []);
    incoming.set(node.id, []);
  }
  for (const edge of allEdges) {
    if (!memberIds.has(edge.fromId) || !memberIds.has(edge.toId)) continue;
    outgoing.get(edge.fromId)!.push(edge.toId);
    incoming.get(edge.toId)!.push(edge.fromId);
  }

  // Layer assignment reuses the global longest-path layering computed
  // by ``buildTopology``. Per component, normalize so the topmost layer
  // starts at zero.
  let minGlobalLayer = Number.POSITIVE_INFINITY;
  for (const node of members) {
    const layer = topology.layer.get(node.id) ?? 0;
    if (layer < minGlobalLayer) minGlobalLayer = layer;
  }
  if (!Number.isFinite(minGlobalLayer)) minGlobalLayer = 0;

  const layerBuckets = new Map<number, AwaitNodeView[]>();
  for (const node of members) {
    const layer = (topology.layer.get(node.id) ?? 0) - minGlobalLayer;
    const bucket = layerBuckets.get(layer) ?? [];
    bucket.push(node);
    layerBuckets.set(layer, bucket);
  }
  // Stable seed ordering: by label. Barycenter sweeps refine this.
  for (const bucket of layerBuckets.values()) {
    bucket.sort((a, b) => a.label.localeCompare(b.label));
  }
  const layerKeys = Array.from(layerBuckets.keys()).sort((a, b) => a - b);

  const indexInLayer = (id: string): number => {
    const layer = (topology.layer.get(id) ?? 0) - minGlobalLayer;
    const bucket = layerBuckets.get(layer);
    if (!bucket) return 0;
    return bucket.findIndex((n) => n.id === id);
  };

  const meanOfRelated = (id: string, edgeMap: Map<string, string[]>): number => {
    const related = edgeMap.get(id) ?? [];
    if (related.length === 0) return Number.POSITIVE_INFINITY;
    let sum = 0;
    let count = 0;
    for (const rid of related) {
      const idx = indexInLayer(rid);
      if (idx < 0) continue;
      sum += idx;
      count += 1;
    }
    return count > 0 ? sum / count : Number.POSITIVE_INFINITY;
  };

  // Median-of-barycenter sweeps. Down passes order each layer by its
  // parents' positions; up passes order by children. A few iterations
  // converge to a layout with very few crossings on typical trees.
  for (let sweep = 0; sweep < BARYCENTER_SWEEPS; sweep += 1) {
    for (let i = 1; i < layerKeys.length; i += 1) {
      const bucket = layerBuckets.get(layerKeys[i]!)!;
      bucket.sort((a, b) => {
        const aMean = meanOfRelated(a.id, incoming);
        const bMean = meanOfRelated(b.id, incoming);
        if (aMean !== bMean) return aMean - bMean;
        return a.label.localeCompare(b.label);
      });
    }
    for (let i = layerKeys.length - 2; i >= 0; i -= 1) {
      const bucket = layerBuckets.get(layerKeys[i]!)!;
      bucket.sort((a, b) => {
        const aMean = meanOfRelated(a.id, outgoing);
        const bMean = meanOfRelated(b.id, outgoing);
        if (aMean !== bMean) return aMean - bMean;
        return a.label.localeCompare(b.label);
      });
    }
  }

  // Figure out the effective span of each layer. Layers that would be
  // wider than ``MAX_LAYER_WIDTH`` get wrapped into sub-rows: a 100-child
  // gather no longer produces a 15000px-wide single strip.
  const PER_ROW = Math.max(8, Math.floor(MAX_LAYER_WIDTH / NODE_SPACING) + 1);
  const layerSpan: Map<number, { width: number; subRows: number }> = new Map();
  for (const layer of layerKeys) {
    const bucket = layerBuckets.get(layer)!;
    const naturalWidth = Math.max(0, bucket.length - 1) * NODE_SPACING;
    if (naturalWidth <= MAX_LAYER_WIDTH || bucket.length <= PER_ROW) {
      layerSpan.set(layer, { width: naturalWidth, subRows: 1 });
    } else {
      const subRows = Math.ceil(bucket.length / PER_ROW);
      const wrappedWidth = Math.max(0, PER_ROW - 1) * NODE_SPACING;
      layerSpan.set(layer, { width: wrappedWidth, subRows });
    }
  }

  // Component's horizontal span = widest layer (after wrapping); the
  // narrower layers center within that span so the tree looks balanced.
  let widestWidth = 0;
  for (const span of layerSpan.values()) {
    if (span.width > widestWidth) widestWidth = span.width;
  }

  // Vertical span advances by one LAYER_SPACING per *visual* row, so a
  // wrapped layer of 3 sub-rows pushes subsequent layers down by 3
  // sub-row units. Sub-rows are tighter than full layer rows because
  // they're cosmetic, not structural.
  const layerY: Map<number, number> = new Map();
  let cursorY = 0;
  for (const layer of layerKeys) {
    layerY.set(layer, cursorY);
    const span = layerSpan.get(layer)!;
    cursorY += LAYER_SPACING + Math.max(0, span.subRows - 1) * SUB_ROW_SPACING;
  }

  const laidOut: LaidOutNode[] = [];
  for (const layer of layerKeys) {
    const bucket = layerBuckets.get(layer)!;
    const span = layerSpan.get(layer)!;
    const baseY = layerY.get(layer)!;
    if (span.subRows === 1) {
      const offsetX = (widestWidth - span.width) / 2;
      bucket.forEach((node, i) => {
        laidOut.push({
          id: node.id,
          kind: node.kind,
          state: node.state,
          label: node.label,
          x: offsetX + i * NODE_SPACING,
          y: baseY,
          isRoot: (topology.inDegree.get(node.id) ?? 0) === 0,
        });
      });
    } else {
      bucket.forEach((node, i) => {
        const subRow = Math.floor(i / PER_ROW);
        const subCol = i % PER_ROW;
        // Each sub-row may be shorter than ``PER_ROW`` on its last
        // line — center the partial row inside the wrapped span.
        const inRowCount = subRow === span.subRows - 1 ? bucket.length - PER_ROW * subRow : PER_ROW;
        const inRowWidth = Math.max(0, inRowCount - 1) * NODE_SPACING;
        const offsetX = (widestWidth - inRowWidth) / 2;
        laidOut.push({
          id: node.id,
          kind: node.kind,
          state: node.state,
          label: node.label,
          x: offsetX + subCol * NODE_SPACING,
          y: baseY + subRow * SUB_ROW_SPACING,
          isRoot: (topology.inDegree.get(node.id) ?? 0) === 0,
        });
      });
    }
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const n of laidOut) {
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x > maxX) maxX = n.x;
    if (n.y > maxY) maxY = n.y;
  }
  if (!Number.isFinite(minX)) {
    minX = 0;
    minY = 0;
    maxX = 0;
    maxY = 0;
  }
  return {
    nodes: laidOut,
    minX,
    minY,
    maxX,
    maxY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

// Translate the freshly-computed layout so the centroid of nodes that
// already had positions in the previous layout stays put. Newly-added
// nodes accept the new layout's positioning; everything else gets the
// same delta applied. The total layout shift across a small update is
// therefore measured by how many new nodes were added — not by which
// component reshuffled in the packing grid.
function stabilizeLayout(
  next: GraphLayout,
  prev: Map<string, { x: number; y: number }>,
): GraphLayout {
  if (prev.size === 0 || next.nodes.length === 0) return next;
  let sumDx = 0;
  let sumDy = 0;
  let count = 0;
  for (const node of next.nodes) {
    const oldPos = prev.get(node.id);
    if (!oldPos) continue;
    sumDx += oldPos.x - node.x;
    sumDy += oldPos.y - node.y;
    count += 1;
  }
  if (count === 0) return next;
  const dx = sumDx / count;
  const dy = sumDy / count;
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return next;
  return {
    nodes: next.nodes.map((n) => ({ ...n, x: n.x + dx, y: n.y + dy })),
    edges: next.edges.map((e) => ({
      ...e,
      fromX: e.fromX + dx,
      fromY: e.fromY + dy,
      toX: e.toX + dx,
      toY: e.toY + dy,
    })),
    bbox: {
      x: next.bbox.x + dx,
      y: next.bbox.y + dy,
      width: next.bbox.width,
      height: next.bbox.height,
    },
  };
}

function buildNeighborhood(
  id: string,
  layout: GraphLayout,
): { nodes: Set<string>; edges: Set<string> } {
  const nodes = new Set<string>([id]);
  const edges = new Set<string>();
  for (const edge of layout.edges) {
    if (edge.fromId === id) {
      edges.add(edge.id);
      nodes.add(edge.toId);
    } else if (edge.toId === id) {
      edges.add(edge.id);
      nodes.add(edge.fromId);
    }
  }
  return { nodes, edges };
}

// ──────────────────────────────────────────────────────────────────────────
// Shared building blocks (mirror QueuesPage / SemaphoresPage)
// ──────────────────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-mono text-[10px] uppercase tracking-widest text-muted">{title}</h2>
      {children}
    </section>
  );
}

function SectionEmpty() {
  return (
    <Card padding="md">
      <p className="font-mono text-xs text-subtle">No data available</p>
    </Card>
  );
}

function SummaryCell({
  label,
  value,
  sub,
  intent = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  intent?: Intent;
}) {
  return (
    <Card padding="sm" intent={intent} className="flex flex-col gap-1">
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <span className="truncate font-mono text-base tabular-nums text-text">{value}</span>
      {sub !== undefined && (
        <span className="truncate font-mono text-[10px] uppercase tracking-widest text-subtle">
          {sub}
        </span>
      )}
    </Card>
  );
}

// ── Formatting ───────────────────────────────────────────────────────────

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds === 0) return "0s";
  if (seconds < 1e-3) return `${(seconds * 1e6).toFixed(0)}µs`;
  if (seconds < 1) return `${(seconds * 1e3).toFixed(1)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m${remainder.toFixed(0).padStart(2, "0")}s`;
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}
