/**
 * Viewport-aware virtualization for the dependency graph.
 *
 * Two stage culling:
 *
 *   1. **Geometric clipping** — see :mod:`AwaitDependencyGeometry`.
 *      Drops nodes / edges fully outside the visible viewport.
 *   2. **Budget cap** — bounds the final draw count so a pathological
 *      graph can't blow past the renderer's per-frame budget.
 *      Overflow is reported so the panel can surface a "+N hidden"
 *      badge.
 */

import {
  clipToViewport,
  edgeIntersectsViewport,
  intersectsViewport,
  type Viewport,
} from "@/dashboard/dependencies/AwaitDependencyGeometry";
import type {
  LaidEdge,
  LaidNode,
  LayoutFrame,
} from "@/dashboard/dependencies/layout/AwaitDependencyLayout";

export interface VirtualizationInputs {
  frame: LayoutFrame;
  viewport: Viewport;
  maxNodes?: number;
  maxEdges?: number;
}

export interface VirtualizationOutput {
  visibleNodes: LaidNode[];
  visibleEdges: LaidEdge[];
  nodeOverflow: number;
  edgeOverflow: number;
}

const DEFAULT_MAX_NODES = 512;
const DEFAULT_MAX_EDGES = 1024;

export function virtualize(
  inputs: VirtualizationInputs,
): VirtualizationOutput {
  const {
    frame,
    viewport,
    maxNodes = DEFAULT_MAX_NODES,
    maxEdges = DEFAULT_MAX_EDGES,
  } = inputs;
  const clippedNodes = clipToViewport(
    frame.laidNodes,
    viewport,
    intersectsViewport,
  );
  const clippedEdges = clipToViewport(
    frame.laidEdges.filter((e) => !e.dangling),
    viewport,
    edgeIntersectsViewport,
  );
  const nodeOverflow = Math.max(0, clippedNodes.length - maxNodes);
  const edgeOverflow = Math.max(0, clippedEdges.length - maxEdges);
  return {
    visibleNodes:
      nodeOverflow === 0
        ? clippedNodes
        : clippedNodes.slice(clippedNodes.length - maxNodes),
    visibleEdges:
      edgeOverflow === 0
        ? clippedEdges
        : clippedEdges.slice(clippedEdges.length - maxEdges),
    nodeOverflow,
    edgeOverflow,
  };
}
