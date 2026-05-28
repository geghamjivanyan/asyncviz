/**
 * Translate runtime envelopes into invalidation events.
 *
 * The delta processor knows the wire shape of every envelope the
 * timeline cares about and emits the *narrowest possible*
 * invalidation:
 *
 *   * ``timeline_delta`` → row + segment invalidation,
 *   * ``warning_delta`` → row invalidation for the affected tasks,
 *   * ``runtime_event`` (task lifecycle) → row invalidation,
 *   * ``runtime_snapshot`` / ``hydration`` → full viewport invalidation,
 *   * ``heartbeat`` / ``system_status`` → no-op for the canvas.
 *
 * Duplicate suppression + sequence-staleness are already handled by
 * the store reducers — the processor trusts the envelope and the
 * store's :type:`StoreSequenceDecision` semantics.
 */

import type {
  RuntimeEnvelope,
  TaskLifecycleEvent,
  TimelineDeltaPayload,
  WarningDeltaPayload,
} from "@/types/runtime";
import type { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";
import {
  invalidateRow,
  invalidateRows,
} from "@/dashboard/timeline/live/TimelineRowInvalidation";
import { invalidateSegment } from "@/dashboard/timeline/live/TimelineSegmentInvalidation";
import {
  invalidateViewport,
  invalidateWarnings,
} from "@/dashboard/timeline/live/TimelineViewportInvalidation";

export interface DeltaProcessOptions {
  /** Number of past sequence ids to treat as already-applied. ``-1``
   *  disables the suppression guard. */
  lastAppliedSequence?: number;
}

export interface DeltaProcessResult {
  /** Whether the processor produced at least one invalidation. */
  invalidated: boolean;
  /** Number of regions pushed. */
  regionsPushed: number;
  /** ``true`` when the envelope was suppressed (duplicate / stale). */
  suppressed: boolean;
  /** Reason the envelope was suppressed, if any. */
  suppressionReason?: "stale" | "duplicate" | "unknown-type";
}

/**
 * Pure processor — no internal state beyond the in-flight tracker
 * the caller hands in. Tests can inject a fresh tracker per envelope.
 */
export class TimelineDeltaProcessor {
  private _processed = 0;
  private _suppressed = 0;
  private _byType = new Map<RuntimeEnvelope["type"], number>();

  /** Push the envelope through the right narrowing path. */
  process(
    envelope: RuntimeEnvelope,
    tracker: TimelineInvalidationTracker,
    options: DeltaProcessOptions = {},
  ): DeltaProcessResult {
    const lastApplied = options.lastAppliedSequence ?? -1;
    if (envelope.sequence !== undefined && envelope.sequence !== null && lastApplied >= 0) {
      if (envelope.sequence <= lastApplied) {
        this._suppressed += 1;
        return { invalidated: false, regionsPushed: 0, suppressed: true, suppressionReason: "stale" };
      }
    }
    this._processed += 1;
    this._byType.set(envelope.type, (this._byType.get(envelope.type) ?? 0) + 1);

    switch (envelope.type) {
      case "timeline_delta":
        return this.processTimelineDelta(envelope, tracker);
      case "warning_delta":
        return this.processWarningDelta(envelope, tracker);
      case "runtime_event":
        return this.processRuntimeEvent(envelope, tracker);
      case "runtime_snapshot":
        invalidateViewport(tracker, { sequence: envelope.sequence ?? null });
        return { invalidated: true, regionsPushed: 1, suppressed: false };
      case "metrics_delta":
      case "heartbeat":
      case "system_status":
      case "protocol_error":
        // Canvas does not depend on these — no invalidation needed.
        return { invalidated: false, regionsPushed: 0, suppressed: false };
      default:
        this._suppressed += 1;
        return {
          invalidated: false,
          regionsPushed: 0,
          suppressed: true,
          suppressionReason: "unknown-type",
        };
    }
  }

  metrics(): { processed: number; suppressed: number; byType: ReadonlyMap<RuntimeEnvelope["type"], number> } {
    return { processed: this._processed, suppressed: this._suppressed, byType: this._byType };
  }

  reset(): void {
    this._processed = 0;
    this._suppressed = 0;
    this._byType.clear();
  }

  // ── private dispatch paths ───────────────────────────────────────

  private processTimelineDelta(
    envelope: RuntimeEnvelope,
    tracker: TimelineInvalidationTracker,
  ): DeltaProcessResult {
    const payload = envelope.payload as unknown as TimelineDeltaPayload;
    if (!payload || typeof payload.task_id !== "string") {
      return { invalidated: false, regionsPushed: 0, suppressed: false };
    }
    const segmentId =
      payload.segment?.segment_id ?? payload.open_segment?.segment_id ?? null;
    if (segmentId !== null) {
      invalidateSegment(tracker, segmentId, payload.task_id, {
        sequence: envelope.sequence ?? null,
      });
    } else {
      invalidateRow(tracker, payload.task_id, { sequence: envelope.sequence ?? null });
    }
    if (payload.kind === "span_finalized") {
      // Span finalization changes both the row state (terminal) and
      // all closed segments — fall back to a row-scope invalidation
      // so the renderer reprojects the whole row.
      invalidateRow(tracker, payload.task_id, { sequence: envelope.sequence ?? null });
    }
    return { invalidated: true, regionsPushed: 1, suppressed: false };
  }

  private processWarningDelta(
    envelope: RuntimeEnvelope,
    tracker: TimelineInvalidationTracker,
  ): DeltaProcessResult {
    const payload = envelope.payload as unknown as WarningDeltaPayload;
    const taskIds = payload?.warning?.related_task_ids ?? [];
    invalidateWarnings(tracker, taskIds, { sequence: envelope.sequence ?? null });
    if (taskIds.length > 0) {
      invalidateRows(tracker, taskIds, { sequence: envelope.sequence ?? null });
    }
    return { invalidated: true, regionsPushed: taskIds.length > 0 ? 2 : 1, suppressed: false };
  }

  private processRuntimeEvent(
    envelope: RuntimeEnvelope,
    tracker: TimelineInvalidationTracker,
  ): DeltaProcessResult {
    const payload = envelope.payload as Partial<TaskLifecycleEvent>;
    if (!payload || typeof payload.task_id !== "string") {
      return { invalidated: false, regionsPushed: 0, suppressed: false };
    }
    invalidateRow(tracker, payload.task_id, { sequence: envelope.sequence ?? null });
    return { invalidated: true, regionsPushed: 1, suppressed: false };
  }
}
