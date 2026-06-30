/**
 * Deterministic builders for freeze-region tests.
 *
 * Each builder accepts overrides + returns a fresh object so tests
 * never accidentally share references.
 */

import type {
  FreezeRegionGeometry,
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

const NS_PER_S = 1e9;

export function makeFreezeRegionView(overrides: Partial<FreezeRegionView> = {}): FreezeRegionView {
  const startSeconds = overrides.startSeconds ?? 1.0;
  const endSeconds = overrides.endSeconds ?? 2.5;
  return {
    groupId: "grp-1",
    warningId: "wrn-1",
    windowId: "win-1",
    runtimeId: "rt-1",
    startSeconds,
    endSeconds,
    durationSeconds: Math.max(0, endSeconds - startSeconds),
    severity: "CRITICAL",
    peakSeverity: "CRITICAL",
    lifecycle: "active",
    state: "active",
    intent: "critical",
    peakLagNs: 800 * 1_000_000,
    captureCount: 3,
    escalationCount: 1,
    taskId: "task-1",
    taskName: "render-loop",
    firstSeenNs: startSeconds * NS_PER_S,
    lastSeenNs: endSeconds * NS_PER_S,
    ...overrides,
  };
}

export function makeFreezeRegionGeometry(
  overrides: Partial<FreezeRegionGeometry> = {},
): FreezeRegionGeometry {
  const xStart = overrides.xStart ?? 100;
  const xEnd = overrides.xEnd ?? 200;
  return {
    groupId: "grp-1",
    xStart,
    xEnd,
    width: Math.max(1.5, xEnd - xStart),
    fullyVisible: true,
    clippedLeft: false,
    clippedRight: false,
    ...overrides,
  };
}
