/**
 * Pure string builders for the dependency-graph aria-live announcements.
 */

import type {
  AwaitEdgeView,
  AwaitNodeView,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";
import {
  edgeKindLabel,
  nodeKindLabel,
  stateLabel,
} from "@/dashboard/dependencies/AwaitDependencySeverity";

export function describeNodeForAccessibility(view: AwaitNodeView): string {
  const pieces: string[] = [
    `${nodeKindLabel(view.kind)} ${view.label}`,
    stateLabel(view.state).toLowerCase(),
  ];
  if (view.kind === "gather") {
    pieces.push(`${view.completedCount}/${view.childCount} children completed`);
    if (view.cancelledCount > 0) pieces.push(`${view.cancelledCount} cancelled`);
    if (view.failedCount > 0) pieces.push(`${view.failedCount} failed`);
    if (view.exceptionType !== null) {
      pieces.push(`raised ${view.exceptionType}`);
    }
  }
  return pieces.join(", ");
}

export function describeTopologyAnnouncement(
  nodes: ReadonlyArray<AwaitNodeView>,
  edges: ReadonlyArray<AwaitEdgeView>,
): string {
  if (nodes.length === 0) return "No await dependencies tracked.";
  const gatherCount = nodes.filter((n) => n.kind === "gather").length;
  const taskCount = nodes.length - gatherCount;
  const cancelled = nodes.filter((n) => n.state === "cancelled").length;
  const failed = nodes.filter((n) => n.state === "failed").length;
  const parts = [
    `${nodes.length} nodes (${gatherCount} gathers, ${taskCount} tasks)`,
    `${edges.length} edges`,
  ];
  if (cancelled > 0) parts.push(`${cancelled} cancelled`);
  if (failed > 0) parts.push(`${failed} failed`);
  return `${parts.join(", ")}.`;
}

export function describeFocusAnnouncement(view: AwaitNodeView): string {
  return `Focused ${nodeKindLabel(view.kind).toLowerCase()} ${view.label}, ${stateLabel(view.state).toLowerCase()}.`;
}

export function describeEdgeForAccessibility(edge: AwaitEdgeView): string {
  return `${edgeKindLabel(edge.kind)} from ${edge.fromId} to ${edge.toId}.`;
}
