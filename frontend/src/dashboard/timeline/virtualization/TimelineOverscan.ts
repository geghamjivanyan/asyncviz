/**
 * Pure overscan strategy helpers.
 *
 * Overscan is the buffer of rows / time the engine keeps loaded
 * beyond the strictly-visible window. Larger buffers eliminate
 * scroll/zoom flashes at the cost of paint time. The helpers here
 * compute the overscan budget from camera velocity + viewport size.
 */

import type { OverscanConfig } from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";
import { DEFAULT_OVERSCAN } from "@/dashboard/timeline/virtualization/models/TimelineVirtualizationModels";

export interface OverscanContext {
  /** Visible time-range duration in seconds. */
  visibleDurationSeconds: number;
  /** Visible row count (post-culling). */
  visibleRowCount: number;
  /** Last observed horizontal pan velocity (seconds / second). */
  panVelocitySeconds?: number;
  /** Last observed vertical scroll velocity (rows / second). */
  scrollVelocityRows?: number;
}

export interface OverscanPolicyOptions {
  rowOverscan?: number;
  timeOverscanSeconds?: number;
  /** Multiplier applied to velocity-driven overscan. ``0`` disables. */
  velocityFactor?: number;
  /** Hard ceilings (defensive — never overscan more than this). */
  maxRowOverscan?: number;
  maxTimeOverscanSeconds?: number;
}

const DEFAULTS: Required<OverscanPolicyOptions> = {
  rowOverscan: DEFAULT_OVERSCAN.rowOverscan,
  timeOverscanSeconds: DEFAULT_OVERSCAN.timeOverscanSeconds,
  velocityFactor: 0.5,
  maxRowOverscan: 32,
  maxTimeOverscanSeconds: 600,
};

/** Pure: derive an overscan config from a context + policy. */
export function resolveOverscan(
  context: OverscanContext,
  policy: OverscanPolicyOptions = {},
): OverscanConfig {
  const merged = { ...DEFAULTS, ...policy };
  let rowOverscan = merged.rowOverscan;
  let timeOverscanSeconds = merged.timeOverscanSeconds;

  if (merged.velocityFactor > 0) {
    if (context.panVelocitySeconds !== undefined && context.panVelocitySeconds !== 0) {
      // pan velocity in seconds per second; one second of look-ahead by default.
      const horizontalLookahead = Math.abs(context.panVelocitySeconds) * merged.velocityFactor;
      timeOverscanSeconds = Math.max(timeOverscanSeconds, horizontalLookahead);
    }
    if (context.scrollVelocityRows !== undefined && context.scrollVelocityRows !== 0) {
      const verticalLookahead = Math.abs(context.scrollVelocityRows) * merged.velocityFactor;
      rowOverscan = Math.max(rowOverscan, Math.ceil(verticalLookahead));
    }
  }

  rowOverscan = Math.min(merged.maxRowOverscan, Math.max(0, Math.floor(rowOverscan)));
  timeOverscanSeconds = Math.min(merged.maxTimeOverscanSeconds, Math.max(0, timeOverscanSeconds));
  return { rowOverscan, timeOverscanSeconds };
}

/** Pure: clamp an overscan to defensive maxima. */
export function clampOverscan(
  overscan: OverscanConfig,
  policy: { maxRowOverscan?: number; maxTimeOverscanSeconds?: number } = {},
): OverscanConfig {
  const maxRow = Math.max(0, Math.floor(policy.maxRowOverscan ?? DEFAULTS.maxRowOverscan));
  const maxTime = Math.max(0, policy.maxTimeOverscanSeconds ?? DEFAULTS.maxTimeOverscanSeconds);
  return {
    rowOverscan: Math.min(maxRow, Math.max(0, Math.floor(overscan.rowOverscan))),
    timeOverscanSeconds: Math.min(maxTime, Math.max(0, overscan.timeOverscanSeconds)),
  };
}
