/**
 * SVG canvas for the await dependency graph.
 *
 * Stateless — driven by a :type:`DependencyFrame`. Renders one
 * focusable button per node (so keyboard navigation + screen readers
 * work) plus a path per edge.
 */

import { memo, useCallback, useEffect, useRef } from "react";
import { cn } from "@/lib/cn";
import type { DependencyFrame } from "@/dashboard/dependencies/AwaitDependencyRenderer";
import { describeNodeForAccessibility } from "@/dashboard/dependencies/AwaitDependencyAccessibility";
import { nodeKindLabel, severityForState, stateLabel } from "@/dashboard/dependencies/AwaitDependencySeverity";
import { getAwaitDependencyPanelMetrics } from "@/dashboard/dependencies/diagnostics/AwaitDependencyMetricsCollector";
import { recordAwaitDependencyTrace } from "@/dashboard/dependencies/diagnostics/AwaitDependencyTracing";
import type { AwaitNodeKind } from "@/dashboard/dependencies/models/AwaitDependencyModels";

export interface AwaitDependencyCanvasProps {
  frame: DependencyFrame;
  selectedNodeId: string | null;
  onSelectNode?: (id: string, kind: AwaitNodeKind) => void;
  className?: string;
}

function edgePath(
  fromX: number, fromY: number, toX: number, toY: number,
): string {
  // Cubic bezier with control points pushed to the midpoint of the
  // gap so edges curve nicely between layers without overlapping.
  const dx = (toX - fromX) / 2;
  const c1x = fromX + dx;
  const c2x = toX - dx;
  return `M ${fromX} ${fromY} C ${c1x} ${fromY}, ${c2x} ${toY}, ${toX} ${toY}`;
}

function AwaitDependencyCanvasImpl({
  frame,
  selectedNodeId,
  onSelectNode,
  className,
}: AwaitDependencyCanvasProps): JSX.Element {
  const renderedRef = useRef(0);

  useEffect(() => {
    getAwaitDependencyPanelMetrics().recordFrameRendered();
    renderedRef.current += 1;
    recordAwaitDependencyTrace({
      kind: "canvas-rendered",
      detail: `nodes=${frame.visibleNodes.length} edges=${frame.visibleEdges.length}`,
    });
  }, [frame.visibleNodes, frame.visibleEdges]);

  const handleSelect = useCallback(
    (id: string, kind: AwaitNodeKind) => () => onSelectNode?.(id, kind),
    [onSelectNode],
  );

  const { width, height } = frame.layout;
  const safeWidth = Math.max(width, 1);
  const safeHeight = Math.max(height, 1);

  return (
    <div
      data-testid="await-dependency-canvas"
      data-node-count={frame.visibleNodes.length}
      data-edge-count={frame.visibleEdges.length}
      data-cycle={frame.layout.cycleDetected ? "true" : undefined}
      className={cn("await-dependency-canvas", className)}
      style={{
        width: `${safeWidth}px`,
        height: `${safeHeight}px`,
        position: "relative",
      }}
    >
      <svg
        className="await-dependency-canvas__edges"
        width={safeWidth}
        height={safeHeight}
        viewBox={`0 0 ${safeWidth} ${safeHeight}`}
        aria-hidden="true"
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        {frame.visibleEdges.map((laid) => (
          <path
            key={laid.edge.id}
            data-testid="await-dependency-edge"
            data-edge-id={laid.edge.id}
            data-edge-kind={laid.edge.kind}
            data-cancelled={laid.edge.cancelled ? "true" : undefined}
            data-failed={laid.edge.failed ? "true" : undefined}
            d={edgePath(laid.fromX, laid.fromY, laid.toX, laid.toY)}
            className="await-dependency-canvas__edge"
            fill="none"
          />
        ))}
      </svg>
      {frame.visibleNodes.map((laid) => {
        const view = laid.node;
        const selected = selectedNodeId === view.id;
        return (
          <button
            key={view.id}
            type="button"
            data-testid="await-dependency-node"
            data-node-id={view.id}
            data-node-kind={view.kind}
            data-severity={severityForState(view.state)}
            data-state={view.state}
            data-selected={selected ? "true" : undefined}
            onClick={handleSelect(view.id, view.kind)}
            aria-pressed={selected}
            aria-label={describeNodeForAccessibility(view)}
            className={cn(
              "await-dependency-canvas__node",
              selected && "await-dependency-canvas__node--selected",
            )}
            style={{
              position: "absolute",
              left: `${laid.x}px`,
              top: `${laid.y}px`,
              width: `${laid.width}px`,
              height: `${laid.height}px`,
            }}
          >
            <span className="await-dependency-canvas__kind">
              {nodeKindLabel(view.kind)}
            </span>
            <span className="await-dependency-canvas__label">{view.label}</span>
            <span className="await-dependency-canvas__state">
              {stateLabel(view.state)}
              {view.kind === "gather" && view.childCount > 0 && (
                <span className="await-dependency-canvas__progress">
                  {" "}
                  · {view.completedCount}/{view.childCount}
                </span>
              )}
            </span>
          </button>
        );
      })}
      {(frame.nodeOverflow > 0 || frame.edgeOverflow > 0) && (
        <span
          className="await-dependency-canvas__overflow"
          data-testid="await-dependency-canvas-overflow"
          style={{ position: "absolute", right: 8, bottom: 8 }}
        >
          +{frame.nodeOverflow} hidden nodes, +{frame.edgeOverflow} hidden edges
        </span>
      )}
    </div>
  );
}

export const AwaitDependencyCanvas = memo(AwaitDependencyCanvasImpl);
