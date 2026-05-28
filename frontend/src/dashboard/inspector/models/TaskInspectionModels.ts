/**
 * Types for the canonical task detail inspector.
 *
 * The inspector projects the runtime store + timeline + warnings +
 * metrics into a single :type:`TaskInspection` shape. Panels read
 * one slice each; the projection is deterministic + memoization-
 * friendly so live updates only rerender the panels that actually
 * changed.
 */

import type {
  ActiveTimelineSegment,
  ActiveWarning,
  TaskLifecycleState,
  TaskSnapshot,
  TaskTransitionRecord,
  TimelineSegment,
} from "@/types/runtime";

/** Coarse lifecycle bucket the inspector uses for badging. */
export type InspectorLifecycleState = TaskLifecycleState | "unknown";

/** Compact summary of a task's lifecycle history. */
export interface InspectorLifecycleSummary {
  state: InspectorLifecycleState;
  createdAtSeconds: number | null;
  completedAtSeconds: number | null;
  durationSeconds: number | null;
  /** ``true`` when the task has reached a terminal state. */
  terminal: boolean;
  /** ``true`` when the task has an open active segment. */
  active: boolean;
  /** Ordered transitions — newest last. */
  transitions: readonly TaskTransitionRecord[];
}

/** Compact timeline summary scoped to one task. */
export interface InspectorTimelineSummary {
  /** Total closed segments. */
  segmentCount: number;
  /** Closed run segments. */
  runSegmentCount: number;
  /** Closed wait segments. */
  waitSegmentCount: number;
  /** Total monotonic run duration in seconds. */
  totalRunSeconds: number;
  /** Total monotonic wait duration in seconds. */
  totalWaitSeconds: number;
  /** Earliest closed-segment start in seconds. */
  firstSegmentStartSeconds: number | null;
  /** Latest closed-segment end in seconds. */
  lastSegmentEndSeconds: number | null;
  /** Optional active (still-running) segment. */
  activeSegment: ActiveTimelineSegment | null;
  /** Latest closed segments — newest last, capped for inspector
   *  size. */
  recentSegments: readonly TimelineSegment[];
}

/** Lineage summary — parent + child task ids. */
export interface InspectorRelationships {
  parentTaskId: string | null;
  rootTaskId: string | null;
  depth: number;
  ancestorChain: readonly string[];
  childTaskIds: readonly string[];
  siblingCount: number;
}

/** Warning summary scoped to a task. */
export interface InspectorWarningsSummary {
  active: readonly ActiveWarning[];
  /** Most-recent severity, when the row carries any warning. */
  highestSeverity: ActiveWarning["severity"] | null;
  count: number;
}

/** Per-task metrics roll-up. */
export interface InspectorMetricsSummary {
  /** Fraction of the task's lifetime spent running. */
  runRatio: number | null;
  /** Fraction of the task's lifetime spent waiting. */
  waitRatio: number | null;
  /** Average closed-segment duration in seconds. */
  averageSegmentSeconds: number | null;
  /** Longest closed-segment duration in seconds. */
  maxSegmentSeconds: number | null;
  /** Coroutine throughput hint when the runtime exposes one. */
  coroutineThroughputPerSecond: number | null;
}

/** Replay metadata snapshot. */
export interface InspectorReplaySummary {
  /** Oldest replayable sequence the runtime currently retains. */
  oldestRetainedSequence: number | null;
  /** Newest replayable sequence the runtime currently retains. */
  newestRetainedSequence: number | null;
  /** Whether the runtime's replay buffer can still cover the active
   *  reconnect window. */
  windowHit: boolean;
  /** Latest store sequence — the cursor for live updates. */
  lastSequence: number;
}

/** Inspector projection. The container builds one of these and the
 *  panels consume slices. */
export interface TaskInspection {
  /** ``null`` when no task is selected. */
  task: TaskSnapshot | null;
  state: InspectorLifecycleState;
  lifecycle: InspectorLifecycleSummary;
  timeline: InspectorTimelineSummary;
  relationships: InspectorRelationships;
  warnings: InspectorWarningsSummary;
  metrics: InspectorMetricsSummary;
  replay: InspectorReplaySummary;
  /** Stable generation that flips on every projection rebuild. */
  generation: number;
}

/** Sentinel projection used by hooks before data hydrates. */
export const EMPTY_TASK_INSPECTION: TaskInspection = Object.freeze({
  task: null,
  state: "unknown" as InspectorLifecycleState,
  lifecycle: {
    state: "unknown" as InspectorLifecycleState,
    createdAtSeconds: null,
    completedAtSeconds: null,
    durationSeconds: null,
    terminal: false,
    active: false,
    transitions: Object.freeze([]) as readonly TaskTransitionRecord[],
  },
  timeline: {
    segmentCount: 0,
    runSegmentCount: 0,
    waitSegmentCount: 0,
    totalRunSeconds: 0,
    totalWaitSeconds: 0,
    firstSegmentStartSeconds: null,
    lastSegmentEndSeconds: null,
    activeSegment: null,
    recentSegments: Object.freeze([]) as readonly TimelineSegment[],
  },
  relationships: {
    parentTaskId: null,
    rootTaskId: null,
    depth: 0,
    ancestorChain: Object.freeze([]) as readonly string[],
    childTaskIds: Object.freeze([]) as readonly string[],
    siblingCount: 0,
  },
  warnings: {
    active: Object.freeze([]) as readonly ActiveWarning[],
    highestSeverity: null,
    count: 0,
  },
  metrics: {
    runRatio: null,
    waitRatio: null,
    averageSegmentSeconds: null,
    maxSegmentSeconds: null,
    coroutineThroughputPerSecond: null,
  },
  replay: {
    oldestRetainedSequence: null,
    newestRetainedSequence: null,
    windowHit: false,
    lastSequence: 0,
  },
  generation: 0,
});

/** Canonical panel identifier — used for tab persistence + tracing. */
export type InspectorPanelKind =
  | "overview"
  | "timeline"
  | "metrics"
  | "warnings"
  | "relationships"
  | "events"
  | "replay"
  | "lifecycle"
  | "metadata"
  | "diagnostics";

export const INSPECTOR_PANEL_ORDER: readonly InspectorPanelKind[] = Object.freeze([
  "overview",
  "timeline",
  "lifecycle",
  "relationships",
  "warnings",
  "metrics",
  "events",
  "metadata",
  "replay",
  "diagnostics",
]);
