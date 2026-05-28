/**
 * Zustand store for the await-dependency graph.
 *
 * Owns the topology — a node map + an edge map — synthesized from the
 * streamed asyncio.gather.* event timeline. The store is intentionally
 * normalized: nodes keyed by id (task id or gather id), edges keyed by
 * a deterministic edge id of the form ``"<kind>:<fromId>-><toId>"``.
 *
 * Pure reducers (``reduceEventPayload``, ``ensureNode``, ``ensureEdge``,
 * ``finalizeNode``) live alongside the actions so tests can exercise
 * them without a Zustand instance.
 *
 * Replay safety: live ingest and replay rebuild flow through the same
 * ``applyEventPayload`` reducer, so a deterministic event stream
 * produces bit-identical topology.
 */

import { create } from "zustand";
import type {
  AwaitEdgeKind,
  AwaitEdgeRecord,
  AwaitGatherEventPayload,
  AwaitNodeRecord,
  GatherCancelledPayload,
  GatherChildAttachedPayload,
  GatherChildCompletedPayload,
  GatherCompletedPayload,
  GatherCreatedPayload,
  GatherFailedPayload,
  GatherWaitStartedPayload,
} from "@/dashboard/dependencies/models/AwaitDependencyModels";

export const DEFAULT_MAX_NODES = 4096;

// ── reconciliation stats ────────────────────────────────────────────────

export interface AwaitDependencyStoreStats {
  eventsApplied: number;
  eventsDropped: number;
  nodesCreated: number;
  edgesCreated: number;
  nodesEvicted: number;
  lastEventAtMs: number;
}

const INITIAL_STATS: AwaitDependencyStoreStats = {
  eventsApplied: 0,
  eventsDropped: 0,
  nodesCreated: 0,
  edgesCreated: 0,
  nodesEvicted: 0,
  lastEventAtMs: 0,
};

export type AwaitDependencyStoreStatus =
  | "idle"
  | "loading"
  | "ready"
  | "error";

export interface AwaitDependencyStoreState {
  nodesById: Record<string, AwaitNodeRecord>;
  /** Insertion-order list — keeps the layered layout stable across renders. */
  nodeIds: string[];
  edgesById: Record<string, AwaitEdgeRecord>;
  edgeIds: string[];
  selectedNodeId: string | null;
  maxNodes: number;
  status: AwaitDependencyStoreStatus;
  errorMessage: string | null;
  stats: AwaitDependencyStoreStats;

  applyEventPayload: (payload: AwaitGatherEventPayload) => void;
  setSelectedNode: (id: string | null) => void;
  markLoading: () => void;
  markError: (message: string) => void;
  setMaxNodes: (cap: number) => void;
  reset: () => void;
}

// ── pure reducer helpers ────────────────────────────────────────────────

function nowNs(): number {
  return typeof performance !== "undefined"
    ? Math.floor(performance.now() * 1_000_000)
    : Date.now() * 1_000_000;
}

function freshTaskNode(id: string, label: string, ns: number): AwaitNodeRecord {
  return {
    id,
    kind: "task",
    label,
    state: "running",
    parentTaskId: null,
    childCount: 0,
    completedCount: 0,
    cancelledCount: 0,
    failedCount: 0,
    sequence: 0,
    firstSeenNs: ns,
    lastSeenNs: ns,
    exceptionType: null,
    durationSeconds: null,
  };
}

function freshGatherNode(
  id: string,
  parentTaskId: string | null,
  childCount: number,
  ns: number,
): AwaitNodeRecord {
  return {
    id,
    kind: "gather",
    label: id,
    state: "pending",
    parentTaskId,
    childCount,
    completedCount: 0,
    cancelledCount: 0,
    failedCount: 0,
    sequence: 0,
    firstSeenNs: ns,
    lastSeenNs: ns,
    exceptionType: null,
    durationSeconds: null,
  };
}

function freshEdge(
  kind: AwaitEdgeKind,
  fromId: string,
  toId: string,
  childIndex: number | null,
  ns: number,
): AwaitEdgeRecord {
  return {
    id: `${kind}:${fromId}->${toId}`,
    kind,
    fromId,
    toId,
    childIndex,
    completed: false,
    cancelled: false,
    failed: false,
    firstSeenNs: ns,
    lastSeenNs: ns,
  };
}

interface MutableTopology {
  nodesById: Record<string, AwaitNodeRecord>;
  nodeIds: string[];
  edgesById: Record<string, AwaitEdgeRecord>;
  edgeIds: string[];
  nodesCreated: number;
  edgesCreated: number;
  nodesEvicted: number;
}

function snapshotMutable(state: AwaitDependencyStoreState): MutableTopology {
  return {
    nodesById: { ...state.nodesById },
    nodeIds: [...state.nodeIds],
    edgesById: { ...state.edgesById },
    edgeIds: [...state.edgeIds],
    nodesCreated: 0,
    edgesCreated: 0,
    nodesEvicted: 0,
  };
}

function ensureNode(
  topology: MutableTopology,
  id: string,
  factory: (ns: number) => AwaitNodeRecord,
  ns: number,
  maxNodes: number,
): AwaitNodeRecord | null {
  const existing = topology.nodesById[id];
  if (existing !== undefined) {
    existing.lastSeenNs = ns;
    return existing;
  }
  if (topology.nodeIds.length >= maxNodes) {
    topology.nodesEvicted += 1;
    return null;
  }
  const node = factory(ns);
  topology.nodesById[id] = node;
  topology.nodeIds.push(id);
  topology.nodesCreated += 1;
  return node;
}

function ensureEdge(
  topology: MutableTopology,
  kind: AwaitEdgeKind,
  fromId: string,
  toId: string,
  childIndex: number | null,
  ns: number,
): AwaitEdgeRecord | null {
  const id = `${kind}:${fromId}->${toId}`;
  const existing = topology.edgesById[id];
  if (existing !== undefined) {
    existing.lastSeenNs = ns;
    if (childIndex !== null && existing.childIndex === null) {
      existing.childIndex = childIndex;
    }
    return existing;
  }
  // Don't create edges for nodes that don't exist yet (defensive — the
  // caller should have invoked ``ensureNode`` first). Returning null lets
  // the reducer skip without throwing.
  if (!(fromId in topology.nodesById) || !(toId in topology.nodesById)) {
    return null;
  }
  const edge = freshEdge(kind, fromId, toId, childIndex, ns);
  topology.edgesById[id] = edge;
  topology.edgeIds.push(id);
  topology.edgesCreated += 1;
  return edge;
}

function finalizeNode(
  topology: MutableTopology,
  id: string,
  state: AwaitNodeRecord["state"],
  ns: number,
  patch?: Partial<AwaitNodeRecord>,
): void {
  const existing = topology.nodesById[id];
  if (existing === undefined) return;
  topology.nodesById[id] = {
    ...existing,
    ...patch,
    state,
    lastSeenNs: ns,
    sequence: existing.sequence + 1,
  };
}

function markChildEdge(
  topology: MutableTopology,
  fromId: string,
  toId: string,
  ns: number,
  patch: Partial<AwaitEdgeRecord>,
): void {
  const id = `fanout:${fromId}->${toId}`;
  const existing = topology.edgesById[id];
  if (existing === undefined) return;
  topology.edgesById[id] = { ...existing, ...patch, lastSeenNs: ns };
}

// ── per-event reducers ─────────────────────────────────────────────────

function applyCreated(
  topology: MutableTopology,
  payload: GatherCreatedPayload,
  ns: number,
  maxNodes: number,
): void {
  // Parent task node (synthesize a placeholder if we haven't seen task
  // events yet — the gather edges still want an anchor).
  const parentId = payload.parent_task_id;
  if (parentId !== null) {
    ensureNode(
      topology,
      parentId,
      (n) => freshTaskNode(parentId, parentId, n),
      ns,
      maxNodes,
    );
  }
  // Gather node.
  const gatherId = payload.gather_id;
  ensureNode(
    topology,
    gatherId,
    (n) => freshGatherNode(gatherId, parentId, payload.child_count, n),
    ns,
    maxNodes,
  );
  // Parent → gather edge.
  if (parentId !== null) {
    ensureEdge(topology, "awaits", parentId, gatherId, null, ns);
  }
  // Child nodes + fanout edges declared up-front from ``child_task_ids``.
  payload.child_task_ids.forEach((cid, index) => {
    ensureNode(
      topology,
      cid,
      (n) => freshTaskNode(cid, cid, n),
      ns,
      maxNodes,
    );
    ensureEdge(topology, "fanout", gatherId, cid, index, ns);
  });
}

function applyChildAttached(
  topology: MutableTopology,
  payload: GatherChildAttachedPayload,
  ns: number,
  maxNodes: number,
): void {
  ensureNode(
    topology,
    payload.child_task_id,
    (n) => freshTaskNode(payload.child_task_id, payload.child_task_id, n),
    ns,
    maxNodes,
  );
  ensureEdge(
    topology,
    "fanout",
    payload.gather_id,
    payload.child_task_id,
    payload.child_index,
    ns,
  );
}

function applyWaitStarted(
  topology: MutableTopology,
  payload: GatherWaitStartedPayload,
  ns: number,
): void {
  finalizeNode(topology, payload.gather_id, "running", ns);
}

function applyChildCompleted(
  topology: MutableTopology,
  payload: GatherChildCompletedPayload,
  ns: number,
): void {
  const childState = payload.cancelled
    ? "cancelled"
    : payload.failed
    ? "failed"
    : "completed";
  finalizeNode(topology, payload.child_task_id, childState, ns);
  markChildEdge(topology, payload.gather_id, payload.child_task_id, ns, {
    completed: true,
    cancelled: payload.cancelled,
    failed: payload.failed,
  });
  // Bump gather aggregates.
  const gather = topology.nodesById[payload.gather_id];
  if (gather !== undefined) {
    topology.nodesById[payload.gather_id] = {
      ...gather,
      completedCount: payload.completed_count,
      cancelledCount: gather.cancelledCount + (payload.cancelled ? 1 : 0),
      failedCount: gather.failedCount + (payload.failed ? 1 : 0),
      lastSeenNs: ns,
      sequence: gather.sequence + 1,
    };
  }
}

function applyCompleted(
  topology: MutableTopology,
  payload: GatherCompletedPayload,
  ns: number,
): void {
  finalizeNode(topology, payload.gather_id, "completed", ns, {
    completedCount: payload.completed_count,
    durationSeconds: payload.duration_seconds,
  });
}

function applyCancelled(
  topology: MutableTopology,
  payload: GatherCancelledPayload,
  ns: number,
): void {
  finalizeNode(topology, payload.gather_id, "cancelled", ns, {
    completedCount: payload.completed_count,
    durationSeconds: payload.duration_seconds,
  });
}

function applyFailed(
  topology: MutableTopology,
  payload: GatherFailedPayload,
  ns: number,
): void {
  finalizeNode(topology, payload.gather_id, "failed", ns, {
    completedCount: payload.completed_count,
    durationSeconds: payload.duration_seconds,
    exceptionType: payload.exception_type,
  });
}

/** Apply one payload to a snapshot of the topology. Returns the patched
 *  snapshot ready for ``set()`` plus the per-event delta counters. */
export function reduceEventPayload(
  state: AwaitDependencyStoreState,
  payload: AwaitGatherEventPayload,
): {
  topology: MutableTopology;
  applied: boolean;
} {
  const topology = snapshotMutable(state);
  const ns = nowNs();
  let applied = true;
  switch (payload.event_type) {
    case "asyncio.gather.created":
      applyCreated(topology, payload, ns, state.maxNodes);
      break;
    case "asyncio.gather.child.attached":
      applyChildAttached(topology, payload, ns, state.maxNodes);
      break;
    case "asyncio.gather.wait.started":
      applyWaitStarted(topology, payload, ns);
      break;
    case "asyncio.gather.child.completed":
      applyChildCompleted(topology, payload, ns);
      break;
    case "asyncio.gather.completed":
      applyCompleted(topology, payload, ns);
      break;
    case "asyncio.gather.cancelled":
      applyCancelled(topology, payload, ns);
      break;
    case "asyncio.gather.failed":
      applyFailed(topology, payload, ns);
      break;
    default:
      applied = false;
  }
  return { topology, applied };
}

// ── Zustand instance ────────────────────────────────────────────────────

export const useAwaitDependencyStore = create<AwaitDependencyStoreState>(
  (set, get) => ({
    nodesById: {},
    nodeIds: [],
    edgesById: {},
    edgeIds: [],
    selectedNodeId: null,
    maxNodes: DEFAULT_MAX_NODES,
    status: "idle",
    errorMessage: null,
    stats: INITIAL_STATS,

    applyEventPayload(payload) {
      const state = get();
      const { topology, applied } = reduceEventPayload(state, payload);
      if (!applied) {
        set((s) => ({
          stats: { ...s.stats, eventsDropped: s.stats.eventsDropped + 1 },
        }));
        return;
      }
      set((s) => ({
        nodesById: topology.nodesById,
        nodeIds: topology.nodeIds,
        edgesById: topology.edgesById,
        edgeIds: topology.edgeIds,
        status: s.status === "idle" ? "ready" : s.status,
        stats: {
          ...s.stats,
          eventsApplied: s.stats.eventsApplied + 1,
          nodesCreated: s.stats.nodesCreated + topology.nodesCreated,
          edgesCreated: s.stats.edgesCreated + topology.edgesCreated,
          nodesEvicted: s.stats.nodesEvicted + topology.nodesEvicted,
          lastEventAtMs: Date.now(),
        },
      }));
    },

    setSelectedNode(id) {
      set({ selectedNodeId: id });
    },

    markLoading() {
      set({ status: "loading", errorMessage: null });
    },

    markError(message) {
      set({ status: "error", errorMessage: message });
    },

    setMaxNodes(cap) {
      if (cap < 1) return;
      set({ maxNodes: cap });
    },

    reset() {
      set({
        nodesById: {},
        nodeIds: [],
        edgesById: {},
        edgeIds: [],
        selectedNodeId: null,
        status: "idle",
        errorMessage: null,
        stats: INITIAL_STATS,
      });
    },
  }),
);
