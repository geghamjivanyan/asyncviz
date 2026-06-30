/**
 * Stateless presentation layer for the await dependency graph.
 *
 * Mirrors :class:`QueuePressurePanel` + :class:`SemaphoreContentionPanel`.
 * Replay-deterministic: feed the same projection twice and the DOM is
 * identical.
 */

import { memo, useEffect, useMemo, useRef } from "react";
import { cn } from "@/lib/cn";
import { AwaitDependencyCanvas } from "@/dashboard/dependencies/AwaitDependencyCanvas";
import { describeTopologyAnnouncement } from "@/dashboard/dependencies/AwaitDependencyAccessibility";
import type { DependencyFrame } from "@/dashboard/dependencies/AwaitDependencyRenderer";
import type {
  AwaitEdgeView,
  AwaitNodeKind,
  AwaitNodeView,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

export interface AwaitDependencyGraphStatusProps {
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
}

export interface AwaitDependencyGraphProps {
  nodes: ReadonlyArray<AwaitNodeView>;
  edges: ReadonlyArray<AwaitEdgeView>;
  alarmCount: number;
  frame: DependencyFrame;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null, kind: AwaitNodeKind | null) => void;
  status: AwaitDependencyGraphStatusProps;
  className?: string;
}

function AwaitDependencyGraphImpl({
  nodes,
  edges,
  alarmCount,
  frame,
  selectedNodeId,
  onSelectNode,
  status,
  className,
}: AwaitDependencyGraphProps): JSX.Element {
  const announcement = useMemo(() => describeTopologyAnnouncement(nodes, edges), [nodes, edges]);
  const renderCount = useRef(0);

  useEffect(() => {
    renderCount.current += 1;
  }, [nodes, edges]);

  return (
    <section
      data-testid="await-dependency-graph"
      data-node-count={nodes.length}
      data-edge-count={edges.length}
      className={cn("await-dependency-graph", className)}
      aria-labelledby="await-dependency-graph-heading"
    >
      <header className="await-dependency-graph__header">
        <h2 id="await-dependency-graph-heading" className="await-dependency-graph__title">
          Await dependencies
        </h2>
        <span
          className="await-dependency-graph__badge"
          data-testid="await-dependency-alarm-count"
          data-tone={alarmCount > 0 ? "alert" : "calm"}
        >
          {alarmCount} alarm{alarmCount === 1 ? "" : "s"}
        </span>
        <span className="await-dependency-graph__count">
          {nodes.length} node{nodes.length === 1 ? "" : "s"}, {edges.length} edge
          {edges.length === 1 ? "" : "s"}
        </span>
        {status.status === "loading" && (
          <span className="await-dependency-graph__status" data-status="loading">
            loading…
          </span>
        )}
        {status.status === "error" && (
          <span className="await-dependency-graph__status" data-status="error" role="alert">
            {status.errorMessage ?? "failed to build dependency graph"}
          </span>
        )}
      </header>

      <div
        className="await-dependency-graph__sr-only"
        aria-live="polite"
        data-testid="await-dependency-live-region"
      >
        {announcement}
      </div>

      {nodes.length === 0 ? (
        <p className="await-dependency-graph__empty" data-testid="await-dependency-empty">
          No await dependencies tracked yet. Dependency edges will appear here as the runtime emits{" "}
          <code>asyncio.gather</code> events.
        </p>
      ) : (
        <div className="await-dependency-graph__viewport">
          <AwaitDependencyCanvas
            frame={frame}
            selectedNodeId={selectedNodeId}
            onSelectNode={(id, kind) => onSelectNode(id, kind)}
          />
        </div>
      )}
    </section>
  );
}

export const AwaitDependencyGraph = memo(AwaitDependencyGraphImpl);
