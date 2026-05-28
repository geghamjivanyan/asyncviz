/**
 * Zustand store for the blocking-warning dashboard panel.
 *
 * Owns:
 *   * the indexed wire-shape state (``groupsById`` + ``activeIds`` +
 *     ``recentIds``).
 *   * the UI selection / filter state.
 *   * sequence gating so out-of-order websocket frames are dropped.
 *
 * Pure reducers live next to the actions so tests can exercise them
 * without a Zustand instance. Live updates flow through
 * :func:`applyEventPayload`; full hydration uses
 * :func:`hydrateSnapshot`.
 */

import { create } from "zustand";
import type {
  BlockingGroupSeverity,
  BlockingWarningEmitterSnapshot,
  BlockingWarningEventPayload,
  BlockingWarningFilter,
  BlockingWarningFilterMode,
  BlockingWarningGroupModel,
  BlockingWarningTransition,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import {
  DEFAULT_FILTER,
  filterFromMode,
  groupFromEventPayload,
} from "@/dashboard/warnings/blocking/selectors/BlockingWarningSelectors";

// ── reconciliation stats ────────────────────────────────────────────────

export interface BlockingWarningStoreStats {
  hydrationsApplied: number;
  eventsApplied: number;
  eventsDropped: number;
  duplicatesDropped: number;
  staleDropped: number;
  lastEventAtMs: number;
}

const INITIAL_STATS: BlockingWarningStoreStats = {
  hydrationsApplied: 0,
  eventsApplied: 0,
  eventsDropped: 0,
  duplicatesDropped: 0,
  staleDropped: 0,
  lastEventAtMs: 0,
};

// ── store shape ─────────────────────────────────────────────────────────

export interface BlockingWarningStoreState {
  runtimeId: string | null;
  generatedAtMonotonicNs: number;
  configuration: Record<string, unknown>;
  groupsById: Record<string, BlockingWarningGroupModel>;
  activeIds: string[];
  recentIds: string[];
  statistics: BlockingWarningEmitterSnapshot["statistics"] | null;
  metrics: BlockingWarningEmitterSnapshot["metrics"] | null;
  selectedGroupId: string | null;
  filter: BlockingWarningFilter;
  filterMode: BlockingWarningFilterMode;
  lastSequence: number;
  stats: BlockingWarningStoreStats;
  status: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;

  // ── actions ───────────────────────────────────────────────────────────
  hydrateSnapshot: (snapshot: BlockingWarningEmitterSnapshot) => void;
  applyEventPayload: (payload: BlockingWarningEventPayload) => void;
  setSelectedGroup: (groupId: string | null) => void;
  setFilterMode: (mode: BlockingWarningFilterMode) => void;
  setFilter: (filter: BlockingWarningFilter) => void;
  markLoading: () => void;
  markError: (message: string) => void;
  reset: () => void;
}

// ── pure reducer helpers ────────────────────────────────────────────────

const TERMINAL_STATES = new Set(["recovered", "expired"]);

interface HydrationResult {
  groupsById: Record<string, BlockingWarningGroupModel>;
  activeIds: string[];
  recentIds: string[];
}

export function reduceHydration(snapshot: BlockingWarningEmitterSnapshot): HydrationResult {
  const groupsById: Record<string, BlockingWarningGroupModel> = {};
  const activeIds: string[] = [];
  const recentIds: string[] = [];
  for (const group of snapshot.active_groups) {
    groupsById[group.group_id] = group;
    activeIds.push(group.group_id);
  }
  for (const group of snapshot.recent_groups) {
    groupsById[group.group_id] = group;
    recentIds.push(group.group_id);
  }
  return { groupsById, activeIds, recentIds };
}

export type EventAppliedKind = "applied" | "duplicate" | "stale";

export interface ReduceEventOutcome {
  kind: EventAppliedKind;
  next: HydrationResult;
  selectedGroupId: string | null;
  lastSequence: number;
}

/**
 * Pure reducer for one wire event.
 *
 * Drops duplicates (same group_id, same monotonic last_seen_ns *and*
 * same state) — the emitter cooldowns make that rare but the bus may
 * deliver a replayed event during reconnect.
 *
 * Drops stale events whose sequence is below the highest sequence the
 * store has seen.
 */
export function reduceEvent(
  prev: {
    groupsById: Record<string, BlockingWarningGroupModel>;
    activeIds: string[];
    recentIds: string[];
    selectedGroupId: string | null;
    lastSequence: number;
  },
  payload: BlockingWarningEventPayload,
): ReduceEventOutcome {
  if (payload.sequence <= prev.lastSequence) {
    return {
      kind: "stale",
      next: {
        groupsById: prev.groupsById,
        activeIds: prev.activeIds,
        recentIds: prev.recentIds,
      },
      selectedGroupId: prev.selectedGroupId,
      lastSequence: prev.lastSequence,
    };
  }
  const existing = prev.groupsById[payload.group_id];
  if (
    existing !== undefined
    && existing.state === payload.state
    && existing.last_seen_ns === payload.last_seen_ns
  ) {
    return {
      kind: "duplicate",
      next: {
        groupsById: prev.groupsById,
        activeIds: prev.activeIds,
        recentIds: prev.recentIds,
      },
      selectedGroupId: prev.selectedGroupId,
      lastSequence: Math.max(prev.lastSequence, payload.sequence),
    };
  }
  const group = groupFromEventPayload(payload);
  const groupsById = { ...prev.groupsById, [group.group_id]: group };
  const isTerminal = TERMINAL_STATES.has(group.state);
  let activeIds = prev.activeIds;
  let recentIds = prev.recentIds;
  const wasActive = activeIds.includes(group.group_id);
  const wasRecent = recentIds.includes(group.group_id);
  if (isTerminal) {
    if (wasActive) activeIds = activeIds.filter((id) => id !== group.group_id);
    if (!wasRecent) recentIds = [...recentIds, group.group_id];
  } else if (!wasActive) {
    activeIds = [...activeIds, group.group_id];
    if (wasRecent) recentIds = recentIds.filter((id) => id !== group.group_id);
  }
  return {
    kind: "applied",
    next: { groupsById, activeIds, recentIds },
    selectedGroupId: prev.selectedGroupId,
    lastSequence: Math.max(prev.lastSequence, payload.sequence),
  };
}

// ── initial state ──────────────────────────────────────────────────────

const INITIAL_STATE: Omit<
  BlockingWarningStoreState,
  | "hydrateSnapshot"
  | "applyEventPayload"
  | "setSelectedGroup"
  | "setFilterMode"
  | "setFilter"
  | "markLoading"
  | "markError"
  | "reset"
> = {
  runtimeId: null,
  generatedAtMonotonicNs: 0,
  configuration: {},
  groupsById: {},
  activeIds: [],
  recentIds: [],
  statistics: null,
  metrics: null,
  selectedGroupId: null,
  filter: DEFAULT_FILTER,
  filterMode: "all",
  lastSequence: 0,
  stats: INITIAL_STATS,
  status: "idle",
  errorMessage: null,
};

// ── store factory ──────────────────────────────────────────────────────

export const useBlockingWarningStore = create<BlockingWarningStoreState>((set) => ({
  ...INITIAL_STATE,

  hydrateSnapshot: (snapshot) =>
    set((prev) => {
      const reduced = reduceHydration(snapshot);
      const stats: BlockingWarningStoreStats = {
        ...prev.stats,
        hydrationsApplied: prev.stats.hydrationsApplied + 1,
      };
      const selectedStillValid =
        prev.selectedGroupId !== null && reduced.groupsById[prev.selectedGroupId] !== undefined;
      return {
        runtimeId: snapshot.runtime_id,
        generatedAtMonotonicNs: snapshot.generated_at_monotonic_ns,
        configuration: snapshot.configuration,
        groupsById: reduced.groupsById,
        activeIds: reduced.activeIds,
        recentIds: reduced.recentIds,
        statistics: snapshot.statistics,
        metrics: snapshot.metrics,
        selectedGroupId: selectedStillValid ? prev.selectedGroupId : null,
        lastSequence: 0,
        status: "ready",
        errorMessage: null,
        stats,
      };
    }),

  applyEventPayload: (payload) =>
    set((prev) => {
      const outcome = reduceEvent(
        {
          groupsById: prev.groupsById,
          activeIds: prev.activeIds,
          recentIds: prev.recentIds,
          selectedGroupId: prev.selectedGroupId,
          lastSequence: prev.lastSequence,
        },
        payload,
      );
      const now = typeof performance !== "undefined" ? performance.now() : Date.now();
      const stats: BlockingWarningStoreStats = {
        ...prev.stats,
        eventsApplied: prev.stats.eventsApplied + (outcome.kind === "applied" ? 1 : 0),
        eventsDropped: prev.stats.eventsDropped + (outcome.kind === "applied" ? 0 : 1),
        duplicatesDropped: prev.stats.duplicatesDropped + (outcome.kind === "duplicate" ? 1 : 0),
        staleDropped: prev.stats.staleDropped + (outcome.kind === "stale" ? 1 : 0),
        lastEventAtMs: now,
      };
      if (outcome.kind !== "applied") {
        return { stats, lastSequence: outcome.lastSequence };
      }
      return {
        groupsById: outcome.next.groupsById,
        activeIds: outcome.next.activeIds,
        recentIds: outcome.next.recentIds,
        selectedGroupId: outcome.selectedGroupId,
        lastSequence: outcome.lastSequence,
        stats,
      };
    }),

  setSelectedGroup: (groupId) =>
    set((prev) => {
      if (prev.selectedGroupId === groupId) return {};
      return { selectedGroupId: groupId };
    }),

  setFilterMode: (mode) =>
    set((prev) => {
      if (prev.filterMode === mode) return {};
      return { filterMode: mode, filter: filterFromMode(mode) };
    }),

  setFilter: (filter) => set({ filter }),

  markLoading: () =>
    set((prev) => (prev.status === "loading" ? {} : { status: "loading", errorMessage: null })),

  markError: (message) => set({ status: "error", errorMessage: message }),

  reset: () =>
    set({
      ...INITIAL_STATE,
    }),
}));

// ── selector helpers (use outside React) ────────────────────────────────

/** Counts breakdown for the panel header — derived selector. */
export function countActiveBySeverity(
  state: Pick<BlockingWarningStoreState, "groupsById" | "activeIds">,
): Record<BlockingGroupSeverity, number> {
  const counts: Record<BlockingGroupSeverity, number> = {
    NONE: 0,
    WARNING: 0,
    CRITICAL: 0,
    FREEZE: 0,
  };
  for (const id of state.activeIds) {
    const group = state.groupsById[id];
    if (group !== undefined) counts[group.severity] += 1;
  }
  return counts;
}

/**
 * Convenience: list every transition we'd want to subscribe to on the
 * websocket bridge. Used by the live-update hook so the wire list
 * stays a single source of truth.
 */
export const BLOCKING_WARNING_EVENT_TYPES: ReadonlyArray<`runtime.warnings.blocking.${BlockingWarningTransition}`> = [
  "runtime.warnings.blocking.opened",
  "runtime.warnings.blocking.escalated",
  "runtime.warnings.blocking.active",
  "runtime.warnings.blocking.recovered",
  "runtime.warnings.blocking.expired",
];
