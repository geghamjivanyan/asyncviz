/**
 * Pointer + keyboard hit-testing for the dependency graph.
 *
 * Operates on the layout output so the canvas / SVG layer doesn't need
 * to know about pan/zoom — the viewport math lives in
 * :mod:`AwaitDependencyGeometry`.
 */

import type { LaidNode } from "@/dashboard/dependencies/layout/AwaitDependencyLayout";
import type { AwaitNodeView } from "@/dashboard/dependencies/models/AwaitDependencyModels";

/** Return the node whose AABB contains the pointer, or null. */
export function nodeAt(
  laidNodes: ReadonlyArray<LaidNode>,
  pointerX: number,
  pointerY: number,
): LaidNode | null {
  for (const laid of laidNodes) {
    if (
      pointerX >= laid.x &&
      pointerX <= laid.x + laid.width &&
      pointerY >= laid.y &&
      pointerY <= laid.y + laid.height
    ) {
      return laid;
    }
  }
  return null;
}

/** Keyboard nav: step to the next / previous node in render order. */
export function neighborNodeId(
  nodes: ReadonlyArray<AwaitNodeView>,
  currentId: string | null,
  direction: 1 | -1,
): string | null {
  if (nodes.length === 0) return null;
  if (currentId === null) {
    return direction === 1 ? nodes[0].id : nodes[nodes.length - 1].id;
  }
  const idx = nodes.findIndex((n) => n.id === currentId);
  if (idx === -1) return nodes[0].id;
  const next = idx + direction;
  if (next < 0 || next >= nodes.length) return currentId;
  return nodes[next].id;
}
