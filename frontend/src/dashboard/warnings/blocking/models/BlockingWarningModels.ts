/**
 * Wire-shape mirrors of the backend ``BlockingWarningEmitter`` snapshot
 * + ``BlockingWarningPayload`` events.
 *
 * The frontend uses these as both the API response shape (lean snapshot
 * endpoint) and the websocket event payload shape. The runtime event
 * envelope wraps these as ``GenericEvent.payload`` with one of the five
 * transition event types (``opened`` / ``escalated`` / ``active`` /
 * ``recovered`` / ``expired``).
 *
 * No business logic lives here — these are pure DTOs. Reducers + views
 * read them and project into the view-model types below.
 */

/** Group lifecycle state. Mirrors backend ``BlockingWarningGroupState``. */
export type BlockingGroupState = "opened" | "escalating" | "active" | "recovered" | "expired";

/** Per-sample classifier severity. Mirrors backend ``BlockingSeverity`` name. */
export type BlockingGroupSeverity = "NONE" | "WARNING" | "CRITICAL" | "FREEZE";

/** Lifecycle transition kind emitted as one event each. */
export type BlockingWarningTransition = "opened" | "escalated" | "active" | "recovered" | "expired";

/** One severity escalation entry, mirrors backend ``EscalationEntry``. */
export interface BlockingEscalationEntry {
  from_severity: BlockingGroupSeverity;
  to_severity: BlockingGroupSeverity;
  monotonic_ns: number;
  sample_index: number | null;
}

/** Frozen snapshot of one group (active or recent). */
export interface BlockingWarningGroupModel {
  group_id: string;
  warning_id: string;
  runtime_id: string;
  window_id: string | null;
  state: BlockingGroupState;
  severity: BlockingGroupSeverity;
  peak_severity: BlockingGroupSeverity;
  first_seen_ns: number;
  last_seen_ns: number;
  recovered_ns: number | null;
  expired_ns: number | null;
  peak_lag_ns: number;
  last_lag_ns: number;
  violation_count: number;
  escalation_count: number;
  capture_ids: number[];
  escalation_history: BlockingEscalationEntry[];
  task_id: string | null;
  task_name: string | null;
  coroutine_name: string | null;
  /** Derived in :func:`projectGroup`; mirrors backend ``freeze_duration_ns``. */
  freeze_duration_ns: number;
  freeze_duration_ms?: number;
}

/** Emitter self-metrics view (subset; non-exhaustive). */
export interface BlockingWarningEmitterMetricsModel {
  outcomes_observed: number;
  captures_observed: number;
  groups_opened: number;
  groups_recovered: number;
  groups_expired: number;
  transitions_opened: number;
  transitions_escalated: number;
  transitions_active: number;
  transitions_recovered: number;
  transitions_expired: number;
  suppressed_by_policy: number;
  suppressed_by_dedup: number;
  captures_correlated: number;
  captures_uncorrelated: number;
  events_emitted: number;
  events_dropped_backpressure: number;
  events_dropped_emitter: number;
}

/** Lifetime statistics view. */
export interface BlockingWarningEmitterStatisticsModel {
  groups_seen: number;
  groups_recovered: number;
  groups_expired: number;
  groups_by_peak_severity: Record<string, number>;
  total_freeze_duration_ns: number;
  longest_freeze_duration_ns: number;
  longest_freeze_group_id: string | null;
  mean_freeze_duration_ns: number;
  peak_lag_ns: number;
  total_captures_correlated: number;
  top_coroutines: Array<{ coroutine_name: string; warning_count: number }>;
}

/** Lean snapshot returned by ``GET /api/runtime/warnings/blocking``. */
export interface BlockingWarningEmitterSnapshot {
  runtime_id: string;
  state: string;
  generated_at_monotonic_ns: number;
  configuration: Record<string, unknown>;
  statistics: BlockingWarningEmitterStatisticsModel;
  metrics: BlockingWarningEmitterMetricsModel;
  active_groups: BlockingWarningGroupModel[];
  recent_groups: BlockingWarningGroupModel[];
}

/**
 * The wire payload embedded in every emitter event. Mirrors backend
 * ``BlockingWarningPayload`` field-for-field. Each transition is a
 * distinct event_type; the payload carries the post-transition group
 * state in full so the dashboard can update without consulting the
 * snapshot endpoint.
 */
export interface BlockingWarningEventPayload {
  warning_id: string;
  group_id: string;
  runtime_id: string;
  window_id: string | null;
  state: BlockingGroupState;
  severity: BlockingGroupSeverity;
  peak_severity: BlockingGroupSeverity;
  first_seen_ns: number;
  last_seen_ns: number;
  recovered_ns: number | null;
  expired_ns: number | null;
  freeze_duration_ns: number;
  freeze_duration_ms?: number;
  peak_lag_ns: number;
  last_lag_ns: number;
  violation_count: number;
  escalation_count: number;
  capture_ids: number[];
  escalation_history: BlockingEscalationEntry[];
  task_id: string | null;
  task_name: string | null;
  coroutine_name: string | null;
  transition: BlockingWarningTransition;
  sequence: number;
}

// ── View-model types ────────────────────────────────────────────────────

/** Coarse severity-derived intent the UI palette maps from. */
export type BlockingWarningIntent = "info" | "warning" | "critical" | "freeze" | "resolved";

/**
 * Render-ready view model — the panel components consume this rather
 * than the raw wire shape. Projection is pure + memoizable; tests
 * exercise :func:`projectGroup` against frozen fixtures.
 */
export interface BlockingWarningView {
  groupId: string;
  warningId: string;
  windowId: string | null;
  runtimeId: string;
  state: BlockingGroupState;
  severity: BlockingGroupSeverity;
  peakSeverity: BlockingGroupSeverity;
  intent: BlockingWarningIntent;
  firstSeenNs: number;
  lastSeenNs: number;
  recoveredNs: number | null;
  expiredNs: number | null;
  freezeDurationNs: number;
  freezeDurationMs: number;
  peakLagNs: number;
  peakLagMs: number;
  lastLagNs: number;
  lastLagMs: number;
  violationCount: number;
  escalationCount: number;
  captureIds: readonly number[];
  escalationHistory: readonly BlockingEscalationEntry[];
  taskId: string | null;
  taskName: string | null;
  coroutineName: string | null;
  /** ``true`` for OPENED / ESCALATING / ACTIVE. */
  isOpen: boolean;
  /** ``true`` for RECOVERED / EXPIRED. */
  isTerminal: boolean;
  /** Short human-friendly label for the badge ("Active", "Recovered"…). */
  stateLabel: string;
  /** Severity label that matches the intent ("Critical", "Freeze"…). */
  severityLabel: string;
}

/** Filter for which groups to display. */
export interface BlockingWarningFilter {
  /** When set, only groups whose severity is in the set are shown. */
  severities: ReadonlySet<BlockingGroupSeverity> | null;
  /** Only show open groups. */
  activeOnly: boolean;
  /** Only show terminal (recovered/expired) groups. */
  terminalOnly: boolean;
  /** Minimum freeze duration in milliseconds. */
  minFreezeMs: number;
}

/** Filter mode toggle for the filter bar. */
export type BlockingWarningFilterMode = "all" | "active" | "recovered" | "freeze-only";
