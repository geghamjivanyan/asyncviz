/**
 * Pure projection from the wire-shape blocking-warning group to the
 * timeline-side :type:`FreezeRegionView`.
 *
 * Splitting the projection from the panel projection
 * (:func:`projectGroup`) is deliberate — the panel needs more fields
 * (ms durations, labels, escalation history) than the canvas
 * overlay. Keeping the timeline projection lean reduces per-frame
 * work and makes it cheap to memoize.
 */

import type { BlockingWarningGroupModel } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";
import {
  compareFreezeKeys,
  intentForFreeze,
  isTerminalState,
  lifecycleForState,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionSeverity";

const NS_PER_S = 1e9;

/**
 * Project one wire-shape group into the renderer's view-model.
 *
 * Returns ``null`` for groups whose severity is below WARNING (the
 * renderer doesn't paint anything for NONE) — keeps the layer's input
 * surface lean.
 */
export function projectFreezeRegion(group: BlockingWarningGroupModel): FreezeRegionView | null {
  if (group.severity === "NONE" && group.peak_severity === "NONE") return null;
  const startSeconds = group.first_seen_ns / NS_PER_S;
  const endNs = closeoutNsForGroup(group);
  const endSeconds = endNs / NS_PER_S;
  if (!Number.isFinite(startSeconds) || !Number.isFinite(endSeconds)) return null;
  const durationSeconds = Math.max(0, endSeconds - startSeconds);
  return {
    groupId: group.group_id,
    warningId: group.warning_id,
    windowId: group.window_id,
    runtimeId: group.runtime_id,
    startSeconds,
    endSeconds,
    durationSeconds,
    severity: group.severity,
    peakSeverity: group.peak_severity,
    lifecycle: lifecycleForState(group.state),
    state: group.state,
    intent: intentForFreeze(group.severity, group.state),
    peakLagNs: group.peak_lag_ns,
    captureCount: group.capture_ids.length,
    escalationCount: group.escalation_count,
    taskId: group.task_id,
    taskName: group.task_name,
    firstSeenNs: group.first_seen_ns,
    lastSeenNs: endNs,
  };
}

/**
 * Pick the canonical close-out instant for the region span.
 *
 * Order of preference: ``recovered_ns`` > ``expired_ns`` > ``last_seen_ns``.
 * Terminal states that lack both close-out instants fall back to
 * ``last_seen_ns`` so the geometry stays valid.
 */
function closeoutNsForGroup(group: BlockingWarningGroupModel): number {
  if (isTerminalState(group.state)) {
    return group.recovered_ns ?? group.expired_ns ?? group.last_seen_ns;
  }
  return group.last_seen_ns;
}

/**
 * Build a sorted region list from the blocking-warning store index.
 *
 * Pure function — exported so the React hook can memoize the work
 * across re-renders.
 */
export function projectFreezeRegions(
  groups: Readonly<Record<string, BlockingWarningGroupModel>>,
): FreezeRegionView[] {
  const out: FreezeRegionView[] = [];
  for (const groupId in groups) {
    const region = projectFreezeRegion(groups[groupId]);
    if (region !== null) out.push(region);
  }
  out.sort(compareFreezeKeys);
  return out;
}
