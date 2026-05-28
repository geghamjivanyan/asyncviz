/**
 * Deterministic fixture builders for blocking-warning tests.
 *
 * Each helper returns a frozen, mutation-safe object — callers can
 * spread overrides without leaking state into other tests.
 */

import type {
  BlockingEscalationEntry,
  BlockingGroupSeverity,
  BlockingGroupState,
  BlockingWarningEmitterMetricsModel,
  BlockingWarningEmitterSnapshot,
  BlockingWarningEmitterStatisticsModel,
  BlockingWarningEventPayload,
  BlockingWarningGroupModel,
  BlockingWarningTransition,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

const NS_PER_MS = 1_000_000;

export function makeEscalation(
  overrides: Partial<BlockingEscalationEntry> = {},
): BlockingEscalationEntry {
  return {
    from_severity: "WARNING",
    to_severity: "CRITICAL",
    monotonic_ns: 1_500 * NS_PER_MS,
    sample_index: 1,
    ...overrides,
  };
}

export function makeGroup(
  overrides: Partial<BlockingWarningGroupModel> = {},
): BlockingWarningGroupModel {
  const first_seen_ns = overrides.first_seen_ns ?? 1_000 * NS_PER_MS;
  const last_seen_ns = overrides.last_seen_ns ?? 2_500 * NS_PER_MS;
  const freeze_duration_ns =
    overrides.freeze_duration_ns ?? last_seen_ns - first_seen_ns;
  return {
    group_id: "grp-1",
    warning_id: "wrn-1",
    runtime_id: "rt-1",
    window_id: "win-1",
    state: "active" as BlockingGroupState,
    severity: "CRITICAL" as BlockingGroupSeverity,
    peak_severity: "CRITICAL" as BlockingGroupSeverity,
    first_seen_ns,
    last_seen_ns,
    recovered_ns: null,
    expired_ns: null,
    peak_lag_ns: 800 * NS_PER_MS,
    last_lag_ns: 700 * NS_PER_MS,
    violation_count: 7,
    escalation_count: 1,
    capture_ids: [11, 12, 13],
    escalation_history: [makeEscalation()],
    task_id: "task-1",
    task_name: "render-loop",
    coroutine_name: "render_loop()",
    freeze_duration_ns,
    freeze_duration_ms: freeze_duration_ns / NS_PER_MS,
    ...overrides,
  };
}

export function makeStatistics(
  overrides: Partial<BlockingWarningEmitterStatisticsModel> = {},
): BlockingWarningEmitterStatisticsModel {
  return {
    groups_seen: 4,
    groups_recovered: 2,
    groups_expired: 1,
    groups_by_peak_severity: { WARNING: 1, CRITICAL: 2, FREEZE: 1 },
    total_freeze_duration_ns: 5_000 * NS_PER_MS,
    longest_freeze_duration_ns: 2_500 * NS_PER_MS,
    longest_freeze_group_id: "grp-1",
    mean_freeze_duration_ns: 1_250 * NS_PER_MS,
    peak_lag_ns: 1_200 * NS_PER_MS,
    total_captures_correlated: 9,
    top_coroutines: [{ coroutine_name: "render_loop()", warning_count: 3 }],
    ...overrides,
  };
}

export function makeMetrics(
  overrides: Partial<BlockingWarningEmitterMetricsModel> = {},
): BlockingWarningEmitterMetricsModel {
  return {
    outcomes_observed: 12,
    captures_observed: 9,
    groups_opened: 4,
    groups_recovered: 2,
    groups_expired: 1,
    transitions_opened: 4,
    transitions_escalated: 2,
    transitions_active: 5,
    transitions_recovered: 2,
    transitions_expired: 1,
    suppressed_by_policy: 1,
    suppressed_by_dedup: 3,
    captures_correlated: 9,
    captures_uncorrelated: 0,
    events_emitted: 14,
    events_dropped_backpressure: 0,
    events_dropped_emitter: 0,
    ...overrides,
  };
}

export function makeSnapshot(
  overrides: Partial<BlockingWarningEmitterSnapshot> = {},
): BlockingWarningEmitterSnapshot {
  return {
    runtime_id: "rt-1",
    state: "ready",
    generated_at_monotonic_ns: 3_000 * NS_PER_MS,
    configuration: {},
    statistics: makeStatistics(),
    metrics: makeMetrics(),
    active_groups: [makeGroup()],
    recent_groups: [
      makeGroup({
        group_id: "grp-2",
        warning_id: "wrn-2",
        state: "recovered",
        severity: "WARNING",
        peak_severity: "WARNING",
        recovered_ns: 2_400 * NS_PER_MS,
        first_seen_ns: 500 * NS_PER_MS,
        last_seen_ns: 1_800 * NS_PER_MS,
        freeze_duration_ns: 1_300 * NS_PER_MS,
        freeze_duration_ms: 1_300,
        window_id: "win-2",
        capture_ids: [21],
        escalation_history: [],
      }),
    ],
    ...overrides,
  };
}

export function makeEvent(
  overrides: Partial<BlockingWarningEventPayload> = {},
): BlockingWarningEventPayload {
  const group = makeGroup();
  const transition: BlockingWarningTransition = "active";
  return {
    warning_id: group.warning_id,
    group_id: group.group_id,
    runtime_id: group.runtime_id,
    window_id: group.window_id,
    state: group.state,
    severity: group.severity,
    peak_severity: group.peak_severity,
    first_seen_ns: group.first_seen_ns,
    last_seen_ns: group.last_seen_ns,
    recovered_ns: group.recovered_ns,
    expired_ns: group.expired_ns,
    freeze_duration_ns: group.freeze_duration_ns,
    freeze_duration_ms: group.freeze_duration_ms,
    peak_lag_ns: group.peak_lag_ns,
    last_lag_ns: group.last_lag_ns,
    violation_count: group.violation_count,
    escalation_count: group.escalation_count,
    capture_ids: [...group.capture_ids],
    escalation_history: [...group.escalation_history],
    task_id: group.task_id,
    task_name: group.task_name,
    coroutine_name: group.coroutine_name,
    transition,
    sequence: 1,
    ...overrides,
  };
}
