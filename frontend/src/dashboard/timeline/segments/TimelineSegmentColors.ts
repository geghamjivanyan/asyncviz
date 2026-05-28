/**
 * Lifecycle-aware color resolution for segment rendering.
 *
 * Centralises every palette lookup the segment renderer makes so
 * layers never re-derive colors themselves. Keeps colors deterministic
 * and easy to reskin via :type:`TimelineColorPalette` overrides.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type {
  TimelineRowWarningSeverity,
  TimelineSegmentLifecycleState,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import { withAlpha } from "@/dashboard/timeline/rows/TimelineRowColors";

/** Base fill color for a segment in the given lifecycle state. */
export function segmentLifecycleFill(
  palette: TimelineColorPalette,
  state: TimelineSegmentLifecycleState,
): string {
  switch (state) {
    case "running":
      return palette.success;
    case "waiting":
    case "sleeping":
      return palette.warning;
    case "blocked":
      return palette.danger;
    case "completed":
      return palette.muted;
    case "cancelled":
      return palette.warning;
    case "failed":
      return palette.danger;
    case "replaying":
      return palette.accent;
    case "orphaned":
      return palette.subtle;
    case "unknown":
    default:
      return palette.accent;
  }
}

/** Active-segment outline (running glow). */
export function segmentActiveStroke(palette: TimelineColorPalette): string {
  return palette.accent;
}

/** Hatch / texture stroke color for waiting + sleeping states. */
export function segmentHatchStroke(palette: TimelineColorPalette): string {
  return withAlpha(palette.text, 0.18);
}

/** Outline color when a segment carries a warning. */
export function segmentWarningStroke(
  palette: TimelineColorPalette,
  severity: TimelineRowWarningSeverity,
): string {
  switch (severity) {
    case "critical":
    case "error":
      return palette.danger;
    case "warning":
      return palette.warning;
    case "info":
      return palette.accent;
  }
}

/** Selection outline. */
export function segmentSelectionStroke(palette: TimelineColorPalette): string {
  return palette.selectionStroke;
}

/** Selection background tint. */
export function segmentSelectionFill(palette: TimelineColorPalette): string {
  return palette.selectionFill;
}

/** Replay-focus outline. */
export function segmentReplayStroke(palette: TimelineColorPalette): string {
  return palette.accent;
}

/** Replay-focus fill tint. */
export function segmentReplayFill(palette: TimelineColorPalette): string {
  return withAlpha(palette.accent, 0.18);
}

/** Cancelled "strike" overlay color. */
export function segmentCancelStrike(palette: TimelineColorPalette): string {
  return withAlpha(palette.text, 0.4);
}

/** Failed inner border color. */
export function segmentFailedBorder(palette: TimelineColorPalette): string {
  return palette.danger;
}
