/**
 * Viewport-clipping helpers for the await dependency graph.
 *
 * Pure math — no DOM. The renderer feeds the layout's full coordinate
 * field through here to compute which nodes / edges intersect the
 * visible window, after pan + zoom.
 */

import type {
  LaidEdge,
  LaidNode,
} from "@/dashboard/dependencies/layout/AwaitDependencyLayout";

export interface Viewport {
  /** Top-left x in layout coords. */
  x: number;
  /** Top-left y in layout coords. */
  y: number;
  width: number;
  height: number;
}

export function intersectsViewport(
  node: LaidNode, viewport: Viewport,
): boolean {
  return !(
    node.x + node.width < viewport.x
    || node.x > viewport.x + viewport.width
    || node.y + node.height < viewport.y
    || node.y > viewport.y + viewport.height
  );
}

export function edgeIntersectsViewport(
  edge: LaidEdge, viewport: Viewport,
): boolean {
  // Approximate AABB of the edge's segment.
  const minX = Math.min(edge.fromX, edge.toX);
  const maxX = Math.max(edge.fromX, edge.toX);
  const minY = Math.min(edge.fromY, edge.toY);
  const maxY = Math.max(edge.fromY, edge.toY);
  return !(
    maxX < viewport.x
    || minX > viewport.x + viewport.width
    || maxY < viewport.y
    || minY > viewport.y + viewport.height
  );
}

export function clipToViewport<T extends LaidNode | LaidEdge>(
  items: ReadonlyArray<T>,
  viewport: Viewport,
  test: (item: T, viewport: Viewport) => boolean,
): T[] {
  const out: T[] = [];
  for (const item of items) {
    if (test(item, viewport)) out.push(item);
  }
  return out;
}
