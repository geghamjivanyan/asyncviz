/**
 * Display vocabulary for await-dependency nodes + edges.
 *
 * Severity here means "how operationally interesting is this node?"
 * Cancelled / failed gathers are the most actionable signal; pending
 * gathers with no completed children for a while are also worth
 * surfacing (future iteration).
 */

import type {
  AwaitEdgeKind,
  AwaitNodeKind,
  AwaitNodeState,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

/** Visual severity bucket — cards + nodes key colors off this. */
export type AwaitNodeSeverity =
  | "calm"
  | "active"
  | "warning"
  | "critical";

const STATE_SEVERITY: Record<AwaitNodeState, AwaitNodeSeverity> = {
  pending: "calm",
  running: "active",
  completed: "calm",
  cancelled: "warning",
  failed: "critical",
};

const STATE_LABELS: Record<AwaitNodeState, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
};

const KIND_LABELS: Record<AwaitNodeKind, string> = {
  task: "Task",
  gather: "Gather",
};

const EDGE_LABELS: Record<AwaitEdgeKind, string> = {
  awaits: "awaits",
  fanout: "fanout",
  cancellation: "cancelled",
};

export function severityForState(state: AwaitNodeState): AwaitNodeSeverity {
  return STATE_SEVERITY[state];
}

export function stateLabel(state: AwaitNodeState): string {
  return STATE_LABELS[state];
}

export function nodeKindLabel(kind: AwaitNodeKind): string {
  return KIND_LABELS[kind];
}

export function edgeKindLabel(kind: AwaitEdgeKind): string {
  return EDGE_LABELS[kind];
}

const SEVERITY_RANK: Record<AwaitNodeSeverity, number> = {
  calm: 0,
  active: 1,
  warning: 2,
  critical: 3,
};

export function compareSeverityDesc(
  a: AwaitNodeSeverity, b: AwaitNodeSeverity,
): number {
  return SEVERITY_RANK[b] - SEVERITY_RANK[a];
}
