/**
 * Pure projection: store records → renderable views.
 *
 * Same pattern as the queue + semaphore projection layers — the
 * renderer + panel both consume the output of this module, never the
 * raw record maps. Memoization is the caller's responsibility.
 */

import type {
  AwaitEdgeRecord,
  AwaitEdgeView,
  AwaitNodeRecord,
  AwaitNodeView,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

export interface AwaitDependencyProjectionInputs {
  nodes: ReadonlyArray<AwaitNodeRecord>;
  edges: ReadonlyArray<AwaitEdgeRecord>;
}

export interface AwaitDependencyProjection {
  nodes: AwaitNodeView[];
  edges: AwaitEdgeView[];
  nodesById: Record<string, AwaitNodeView>;
  /** Number of gather nodes that resolved into a non-calm state. */
  alarmCount: number;
}

export function projectNode(record: AwaitNodeRecord): AwaitNodeView {
  const progress =
    record.kind === "gather" && record.childCount > 0
      ? Math.max(0, Math.min(1, record.completedCount / record.childCount))
      : 0;
  return {
    id: record.id,
    kind: record.kind,
    label: record.label,
    state: record.state,
    parentTaskId: record.parentTaskId,
    childCount: record.childCount,
    completedCount: record.completedCount,
    cancelledCount: record.cancelledCount,
    failedCount: record.failedCount,
    progressRatio: progress,
    exceptionType: record.exceptionType,
    durationSeconds: record.durationSeconds,
  };
}

export function projectEdge(record: AwaitEdgeRecord): AwaitEdgeView {
  return {
    id: record.id,
    kind: record.kind,
    fromId: record.fromId,
    toId: record.toId,
    completed: record.completed,
    cancelled: record.cancelled,
    failed: record.failed,
    childIndex: record.childIndex,
  };
}

export function projectDependencies(
  inputs: AwaitDependencyProjectionInputs,
): AwaitDependencyProjection {
  const nodes = inputs.nodes.map(projectNode);
  const edges = inputs.edges.map(projectEdge);
  const nodesById: Record<string, AwaitNodeView> = {};
  let alarmCount = 0;
  for (const node of nodes) {
    nodesById[node.id] = node;
    if (
      node.kind === "gather"
      && (node.state === "cancelled" || node.state === "failed")
    ) {
      alarmCount += 1;
    }
  }
  return { nodes, edges, nodesById, alarmCount };
}
