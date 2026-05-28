/**
 * Pure projection from the wire shape to the view model.
 *
 * Selectors are deterministic on their inputs — the same group model
 * always produces the same :type:`BlockingWarningView`. Memoized at
 * the hook layer; tests exercise the raw functions.
 */

import type {
  BlockingGroupSeverity,
  BlockingGroupState,
  BlockingWarningEventPayload,
  BlockingWarningFilter,
  BlockingWarningFilterMode,
  BlockingWarningGroupModel,
  BlockingWarningIntent,
  BlockingWarningView,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

// ── constants ───────────────────────────────────────────────────────────

const SEVERITY_RANK: Record<BlockingGroupSeverity, number> = {
  NONE: 0,
  WARNING: 1,
  CRITICAL: 2,
  FREEZE: 3,
};

const STATE_LABEL: Record<BlockingGroupState, string> = {
  opened: "Opened",
  escalating: "Escalating",
  active: "Active",
  recovered: "Recovered",
  expired: "Expired",
};

const SEVERITY_LABEL: Record<BlockingGroupSeverity, string> = {
  NONE: "None",
  WARNING: "Warning",
  CRITICAL: "Critical",
  FREEZE: "Freeze",
};

const TERMINAL_STATES: ReadonlySet<BlockingGroupState> = new Set(["recovered", "expired"]);

/** All severities, ordered high → low for filter chips. */
export const BLOCKING_SEVERITIES: readonly BlockingGroupSeverity[] = [
  "FREEZE",
  "CRITICAL",
  "WARNING",
];

// ── intent + label helpers ─────────────────────────────────────────────

/**
 * Map severity + lifecycle state to a UI intent.
 *
 * A recovered/expired group is rendered as ``"resolved"`` regardless
 * of the peak severity reached during the freeze — the operator no
 * longer needs to act on it.
 */
export function intentFor(
  severity: BlockingGroupSeverity,
  state: BlockingGroupState,
): BlockingWarningIntent {
  if (TERMINAL_STATES.has(state)) return "resolved";
  if (severity === "FREEZE") return "freeze";
  if (severity === "CRITICAL") return "critical";
  if (severity === "WARNING") return "warning";
  return "info";
}

/** Stable ordering: open > terminal; within bucket, by severity then most recent. */
export function compareViews(a: BlockingWarningView, b: BlockingWarningView): number {
  if (a.isOpen !== b.isOpen) return a.isOpen ? -1 : 1;
  const sevDelta = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity];
  if (sevDelta !== 0) return sevDelta;
  return b.lastSeenNs - a.lastSeenNs;
}

// ── projection ──────────────────────────────────────────────────────────

const NS_PER_MS = 1_000_000;

/**
 * Build a render-ready view from a wire-shape group.
 *
 * Pure function — no clock reads, no allocations beyond the returned
 * object. Memoized at the hook level via a (group_id, last_seen_ns,
 * state) key so live updates only re-project the affected group.
 */
export function projectGroup(group: BlockingWarningGroupModel): BlockingWarningView {
  const isTerminal = TERMINAL_STATES.has(group.state);
  const isOpen = !isTerminal;
  const intent = intentFor(group.severity, group.state);
  return {
    groupId: group.group_id,
    warningId: group.warning_id,
    windowId: group.window_id,
    runtimeId: group.runtime_id,
    state: group.state,
    severity: group.severity,
    peakSeverity: group.peak_severity,
    intent,
    firstSeenNs: group.first_seen_ns,
    lastSeenNs: group.last_seen_ns,
    recoveredNs: group.recovered_ns,
    expiredNs: group.expired_ns,
    freezeDurationNs: group.freeze_duration_ns,
    freezeDurationMs:
      group.freeze_duration_ms ?? group.freeze_duration_ns / NS_PER_MS,
    peakLagNs: group.peak_lag_ns,
    peakLagMs: group.peak_lag_ns / NS_PER_MS,
    lastLagNs: group.last_lag_ns,
    lastLagMs: group.last_lag_ns / NS_PER_MS,
    violationCount: group.violation_count,
    escalationCount: group.escalation_count,
    captureIds: group.capture_ids,
    escalationHistory: group.escalation_history,
    taskId: group.task_id,
    taskName: group.task_name,
    coroutineName: group.coroutine_name,
    isOpen,
    isTerminal,
    stateLabel: STATE_LABEL[group.state],
    severityLabel: SEVERITY_LABEL[group.severity],
  };
}

/**
 * Coerce an emitter event payload into the same wire-group shape that
 * :func:`projectGroup` consumes. Lets the live-update reducer reuse
 * the projection without a separate code path per event type.
 */
export function groupFromEventPayload(
  payload: BlockingWarningEventPayload,
): BlockingWarningGroupModel {
  return {
    group_id: payload.group_id,
    warning_id: payload.warning_id,
    runtime_id: payload.runtime_id,
    window_id: payload.window_id,
    state: payload.state,
    severity: payload.severity,
    peak_severity: payload.peak_severity,
    first_seen_ns: payload.first_seen_ns,
    last_seen_ns: payload.last_seen_ns,
    recovered_ns: payload.recovered_ns,
    expired_ns: payload.expired_ns,
    peak_lag_ns: payload.peak_lag_ns,
    last_lag_ns: payload.last_lag_ns,
    violation_count: payload.violation_count,
    escalation_count: payload.escalation_count,
    capture_ids: payload.capture_ids,
    escalation_history: payload.escalation_history,
    task_id: payload.task_id,
    task_name: payload.task_name,
    coroutine_name: payload.coroutine_name,
    freeze_duration_ns: payload.freeze_duration_ns,
    freeze_duration_ms: payload.freeze_duration_ms,
  };
}

// ── filtering ───────────────────────────────────────────────────────────

export const DEFAULT_FILTER: BlockingWarningFilter = {
  severities: null,
  activeOnly: false,
  terminalOnly: false,
  minFreezeMs: 0,
};

/** Build a :type:`BlockingWarningFilter` from the filter mode toggle. */
export function filterFromMode(mode: BlockingWarningFilterMode): BlockingWarningFilter {
  switch (mode) {
    case "active":
      return { ...DEFAULT_FILTER, activeOnly: true };
    case "recovered":
      return { ...DEFAULT_FILTER, terminalOnly: true };
    case "freeze-only":
      return { ...DEFAULT_FILTER, severities: new Set(["FREEZE"]) };
    case "all":
    default:
      return DEFAULT_FILTER;
  }
}

/** Apply a filter to a list of views; returns a *new* array. */
export function applyFilter(
  views: readonly BlockingWarningView[],
  filter: BlockingWarningFilter,
): BlockingWarningView[] {
  const minFreezeMs = filter.minFreezeMs > 0 ? filter.minFreezeMs : 0;
  return views.filter((view) => {
    if (filter.activeOnly && !view.isOpen) return false;
    if (filter.terminalOnly && !view.isTerminal) return false;
    if (filter.severities && !filter.severities.has(view.severity)) return false;
    if (minFreezeMs > 0 && view.freezeDurationMs < minFreezeMs) return false;
    return true;
  });
}

/** Group views by lifecycle bucket — used by the panel for layout. */
export interface BlockingWarningBuckets {
  active: BlockingWarningView[];
  recent: BlockingWarningView[];
}

export function bucketViews(views: readonly BlockingWarningView[]): BlockingWarningBuckets {
  const active: BlockingWarningView[] = [];
  const recent: BlockingWarningView[] = [];
  for (const view of views) {
    if (view.isOpen) {
      active.push(view);
    } else {
      recent.push(view);
    }
  }
  active.sort(compareViews);
  recent.sort(compareViews);
  return { active, recent };
}

/** Counts breakdown for the summary header. */
export interface BlockingWarningCounts {
  total: number;
  active: number;
  recovered: number;
  bySeverity: Record<BlockingGroupSeverity, number>;
}

export function summarize(views: readonly BlockingWarningView[]): BlockingWarningCounts {
  const counts: BlockingWarningCounts = {
    total: views.length,
    active: 0,
    recovered: 0,
    bySeverity: { NONE: 0, WARNING: 0, CRITICAL: 0, FREEZE: 0 },
  };
  for (const view of views) {
    if (view.isOpen) counts.active += 1;
    else counts.recovered += 1;
    counts.bySeverity[view.severity] += 1;
  }
  return counts;
}
