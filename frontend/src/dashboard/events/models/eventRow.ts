/**
 * Canonical projection model for the runtime event feed.
 *
 * The store keeps a bounded ring of :type:`TaskLifecycleEvent`. The
 * feed works on a narrower projection — :type:`EventRow` — that
 * mixes the raw event with timeline / warning / replay annotations
 * the UI cells need.
 *
 * Rows are *immutable*. Reconciliation is reference-based: two rows
 * with the same ``rowKey`` and ``signature`` represent the same event
 * with the same content. Memoized selectors rebuild rows only when
 * the underlying inputs change.
 */

import type { ActiveWarning, TaskLifecycleEvent, WarningSeverity } from "@/types/runtime";

/** Canonical event-row category. */
export type EventCategory =
  | "task.created"
  | "task.started"
  | "task.waiting"
  | "task.resumed"
  | "task.completed"
  | "task.cancelled"
  | "task.failed";

/**
 * UI severity for the row indicator dot. Distinct from warning
 * severity — events without a warning still need an intent for
 * styling (success/danger/etc.) so the row remains scannable.
 */
export type EventRowIntent = "default" | "accent" | "success" | "warning" | "danger";

/** Whether the row was sourced from a replay batch or a live frame. */
export type EventSource = "live" | "replay" | "unknown";

export interface EventRowWarningSummary {
  /** Warnings on the related task at the moment the row was projected. */
  count: number;
  /** Highest severity observed. */
  highestSeverity: WarningSeverity | null;
}

export interface EventRowTimelineSummary {
  /** ``true`` when the related task currently has an open span. */
  hasActiveSegment: boolean;
  /** ``true`` when the row references a known task. */
  taskKnown: boolean;
}

export interface EventRow {
  /** Stable React key — composed from event_id + (sequence | "live"). */
  rowKey: string;
  /** Canonical event id. */
  eventId: string;
  /** Wire event type (``asyncio.task.*``). */
  eventType: TaskLifecycleEvent["event_type"];
  /** Coarser category used by the UI. */
  category: EventCategory;
  /** Color intent used to render the row dot / accent. */
  intent: EventRowIntent;
  /** Display label rendered in the row header. */
  label: string;
  /** Wall-clock seconds the event was generated. */
  timestamp: number;
  /** Monotonic ns from the producer clock. */
  monotonicNs: number;
  /** Reconciled sequence; may be null when the event was rebuilt locally. */
  sequence: number | null;
  /** Task id the event is bound to. */
  taskId: string;
  /** Parent task id. */
  parentTaskId: string | null;
  /** Coroutine name when available. */
  coroutineName: string | null;
  /** Display name for the task. */
  taskName: string | null;
  /** Duration in seconds; only present on terminal events. */
  durationSeconds: number | null;
  /** Exception type — only on failed events. */
  exceptionType: string | null;
  /** Exception message — only on failed events. */
  exceptionMessage: string | null;
  /** Cancellation origin — only on cancelled events. */
  cancellationOrigin: string | null;
  /** ``true`` for terminal task events (completed / cancelled / failed). */
  isTerminal: boolean;
  /** Origin of the row — useful for replay banners. */
  source: EventSource;
  /** Linked warning summary. */
  warnings: EventRowWarningSummary;
  /** Linked timeline summary. */
  timeline: EventRowTimelineSummary;
  /** Optional metadata flattened to a key/value array for display. */
  metadata: ReadonlyArray<readonly [string, string]>;
  /** Signature folds every visible field for memo + tests. */
  signature: string;
}

const CATEGORY_BY_EVENT: Record<TaskLifecycleEvent["event_type"], EventCategory> = {
  "asyncio.task.created": "task.created",
  "asyncio.task.started": "task.started",
  "asyncio.task.waiting": "task.waiting",
  "asyncio.task.resumed": "task.started",
  "asyncio.task.completed": "task.completed",
  "asyncio.task.cancelled": "task.cancelled",
  "asyncio.task.failed": "task.failed",
};

const INTENT_BY_CATEGORY: Record<EventCategory, EventRowIntent> = {
  "task.created": "accent",
  "task.started": "success",
  "task.waiting": "warning",
  "task.resumed": "success",
  "task.completed": "default",
  "task.cancelled": "warning",
  "task.failed": "danger",
};

const TERMINAL_CATEGORIES: ReadonlySet<EventCategory> = new Set([
  "task.completed",
  "task.cancelled",
  "task.failed",
]);

/** Severity-priority helper — same scale used by the metrics module. */
const WARNING_SEVERITY_WEIGHT: Record<WarningSeverity, number> = {
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

/** Pure: pick the highest severity in a warning bucket. */
export function summarizeWarnings(warnings: readonly ActiveWarning[]): EventRowWarningSummary {
  if (warnings.length === 0) return { count: 0, highestSeverity: null };
  let count = 0;
  let highest: WarningSeverity | null = null;
  let weight = 0;
  for (const w of warnings) {
    count += 1;
    const wt = WARNING_SEVERITY_WEIGHT[w.severity];
    if (wt > weight) {
      highest = w.severity;
      weight = wt;
    }
  }
  return { count, highestSeverity: highest };
}

/** Pure: derive the row label from the event + coroutine. */
export function deriveEventLabel(event: TaskLifecycleEvent): string {
  return event.task_name || event.coroutine_name || event.task_id;
}

/** Pure: map a wire event_type to the canonical category. */
export function categoryForEvent(event: TaskLifecycleEvent): EventCategory {
  return CATEGORY_BY_EVENT[event.event_type] ?? "task.created";
}

/** Pure: pick the row's display intent. */
export function intentForCategory(category: EventCategory): EventRowIntent {
  return INTENT_BY_CATEGORY[category];
}

export interface BuildEventRowInputs {
  event: TaskLifecycleEvent;
  warningsForTask: readonly ActiveWarning[];
  taskKnown: boolean;
  hasActiveSegment: boolean;
  source: EventSource;
}

const METADATA_ENTRY_LIMIT = 8;

function flattenMetadata(
  metadata: Record<string, unknown>,
): ReadonlyArray<readonly [string, string]> {
  const entries: Array<readonly [string, string]> = [];
  for (const [key, value] of Object.entries(metadata ?? {})) {
    if (value === null || value === undefined) continue;
    const display =
      typeof value === "string"
        ? value
        : typeof value === "number" || typeof value === "boolean"
          ? String(value)
          : JSON.stringify(value);
    entries.push([key, display]);
    if (entries.length >= METADATA_ENTRY_LIMIT) break;
  }
  return entries;
}

/** Pure: build a single :type:`EventRow` from projection inputs. */
export function buildEventRow(inputs: BuildEventRowInputs): EventRow {
  const { event } = inputs;
  const category = categoryForEvent(event);
  const intent = intentForCategory(category);
  const isTerminal = TERMINAL_CATEGORIES.has(category);
  const warnings = summarizeWarnings(inputs.warningsForTask);
  const duration =
    "duration_seconds" in event && event.duration_seconds != null ? event.duration_seconds : null;
  const exceptionType = event.event_type === "asyncio.task.failed" ? event.exception_type : null;
  const exceptionMessage =
    event.event_type === "asyncio.task.failed" ? event.exception_message : null;
  const cancellationOrigin =
    event.event_type === "asyncio.task.cancelled" ? event.cancellation_origin : null;
  const metadata = flattenMetadata(event.metadata ?? {});
  const sequence =
    "sequence" in event && typeof (event as { sequence?: unknown }).sequence === "number"
      ? ((event as { sequence?: number }).sequence ?? null)
      : null;

  const row: Omit<EventRow, "signature"> = {
    rowKey: `${event.event_id}#${sequence ?? "x"}`,
    eventId: event.event_id,
    eventType: event.event_type,
    category,
    intent:
      warnings.highestSeverity === "critical" || warnings.highestSeverity === "error"
        ? "danger"
        : intent,
    label: deriveEventLabel(event),
    timestamp: event.timestamp,
    monotonicNs: event.monotonic_ns,
    sequence,
    taskId: event.task_id,
    parentTaskId: event.parent_task_id ?? null,
    coroutineName: event.coroutine_name ?? null,
    taskName: event.task_name ?? null,
    durationSeconds: duration,
    exceptionType,
    exceptionMessage,
    cancellationOrigin,
    isTerminal,
    source: inputs.source,
    warnings,
    timeline: {
      hasActiveSegment: inputs.hasActiveSegment,
      taskKnown: inputs.taskKnown,
    },
    metadata,
  };
  return { ...row, signature: signEventRow(row) };
}

export function signEventRow(row: Omit<EventRow, "signature">): string {
  return [
    row.eventId,
    row.eventType,
    row.category,
    row.intent,
    row.label,
    String(row.timestamp),
    String(row.monotonicNs),
    row.sequence ?? "",
    row.taskId,
    row.parentTaskId ?? "",
    row.coroutineName ?? "",
    row.taskName ?? "",
    row.durationSeconds === null ? "" : String(row.durationSeconds),
    row.exceptionType ?? "",
    row.cancellationOrigin ?? "",
    row.isTerminal ? "1" : "0",
    row.source,
    String(row.warnings.count),
    row.warnings.highestSeverity ?? "",
    row.timeline.hasActiveSegment ? "1" : "0",
    row.timeline.taskKnown ? "1" : "0",
    String(row.metadata.length),
  ].join("|");
}

/** Pure: stable comparator — newest first for the feed. */
export function compareEventRowsNewestFirst(a: EventRow, b: EventRow): number {
  if (a.monotonicNs !== b.monotonicNs) return b.monotonicNs - a.monotonicNs;
  const aSeq = a.sequence ?? Number.MIN_SAFE_INTEGER;
  const bSeq = b.sequence ?? Number.MIN_SAFE_INTEGER;
  if (aSeq !== bSeq) return bSeq - aSeq;
  return b.eventId.localeCompare(a.eventId);
}

/** Pure: ascending comparator for cases where chronological ordering is preferred. */
export function compareEventRowsOldestFirst(a: EventRow, b: EventRow): number {
  return -compareEventRowsNewestFirst(a, b);
}
