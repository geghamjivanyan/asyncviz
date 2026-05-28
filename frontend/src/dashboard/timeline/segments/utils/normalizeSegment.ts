/**
 * Pure helper — coerce a (possibly minimal) :type:`TimelineRenderSegment`
 * into a fully-populated :type:`TimelineSegmentProjectionEntry`.
 *
 * Tests + legacy callers may push sparse segments through the scene
 * graph; this helper keeps the segment renderer dependency-tolerant.
 */

import type {
  TimelineRenderSegment,
  TimelineSegmentLifecycleState,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";

const KNOWN_STATES = new Set<TimelineSegmentLifecycleState>([
  "running",
  "waiting",
  "sleeping",
  "blocked",
  "completed",
  "cancelled",
  "failed",
  "replaying",
  "orphaned",
  "unknown",
]);

function inferLifecycle(segment: TimelineRenderSegment): TimelineSegmentLifecycleState {
  if (segment.lifecycleState && KNOWN_STATES.has(segment.lifecycleState)) {
    return segment.lifecycleState;
  }
  switch (segment.intent) {
    case "run":
      return segment.isActive ? "running" : "running";
    case "wait":
      return "waiting";
    case "completed":
      return "completed";
    case "cancelled":
      return "cancelled";
    case "failed":
      return "failed";
    default:
      return "unknown";
  }
}

export function normalizeSegment(
  segment: TimelineRenderSegment,
): TimelineSegmentProjectionEntry {
  const lifecycleState = inferLifecycle(segment);
  const durationSeconds = Math.max(0, segment.endSeconds - segment.startSeconds);
  return {
    ...segment,
    entryId: segment.segmentId,
    lifecycleState,
    sequenceStart: segment.sequenceStart ?? null,
    sequenceEnd: segment.sequenceEnd ?? null,
    durationNs:
      segment.durationNs !== undefined ? segment.durationNs : Math.round(durationSeconds * 1e9),
    warningSeverity: segment.warningSeverity ?? null,
    replay: segment.replay ?? null,
    parentTaskId: segment.parentTaskId ?? null,
    depth: segment.depth ?? 0,
    durationSeconds,
  };
}
