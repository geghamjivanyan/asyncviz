/**
 * Pure styling resolver for lifecycle segments.
 *
 * Translates a :type:`TimelineSegmentProjectionEntry` into the
 * concrete paint instructions the renderer consumes:
 *
 *   * fill color (lifecycle-state driven),
 *   * optional texture overlay (hatch / dots),
 *   * optional stroke (active glow, failed border, warning outline),
 *   * optional cancelled strike overlay,
 *   * selection / replay overlays.
 *
 * The resolver is deterministic for a given (entry, palette,
 * selection, theme) tuple — replay frames produce identical output.
 */

import type { TimelineColorPalette } from "@/dashboard/timeline/rendering/TimelineColors";
import type {
  TimelineRowWarningSeverity,
  TimelineSegmentLifecycleState,
} from "@/dashboard/timeline/rendering/TimelineLayer";
import type { TimelineSegmentProjectionEntry } from "@/dashboard/timeline/segments/models/TimelineSegmentModels";
import {
  segmentActiveStroke,
  segmentCancelStrike,
  segmentFailedBorder,
  segmentHatchStroke,
  segmentLifecycleFill,
  segmentReplayFill,
  segmentReplayStroke,
  segmentSelectionFill,
  segmentSelectionStroke,
  segmentWarningStroke,
} from "@/dashboard/timeline/segments/TimelineSegmentColors";

export type SegmentTextureKind = "none" | "hatch" | "dots";

export interface SegmentStyle {
  /** Base fill applied to the rect. */
  fill: string;
  /** Optional outline color. */
  stroke: string | null;
  /** Outline width in CSS pixels (only honored when ``stroke`` is set). */
  strokeWidth: number;
  /** Optional texture overlay for waiting/sleep/replaying states. */
  texture: SegmentTextureKind;
  /** Texture stroke / dot color when ``texture !== "none"``. */
  textureColor: string;
  /** Optional warning ring color overlaid on the rect. */
  warningStroke: string | null;
  /** ``true`` when a diagonal "cancelled" strike should be drawn. */
  cancelledStrike: boolean;
  /** ``true`` when a failed-state inner border should be drawn. */
  failedBorder: boolean;
  /** Selection overlay (fill + stroke), or ``null``. */
  selection: { fill: string; stroke: string } | null;
  /** Replay overlay (fill + stroke), or ``null``. */
  replay: { fill: string; stroke: string; focused: boolean } | null;
}

export interface SegmentStyleArgs {
  entry: TimelineSegmentProjectionEntry;
  palette: TimelineColorPalette;
  selected: boolean;
}

/** Pure: resolve every paint instruction for a single segment. */
export function resolveSegmentStyle(args: SegmentStyleArgs): SegmentStyle {
  const { entry, palette, selected } = args;
  const lifecycle = entry.lifecycleState;
  const fill = segmentLifecycleFill(palette, lifecycle);
  const texture = textureFor(lifecycle);

  const style: SegmentStyle = {
    fill,
    stroke: entry.isActive ? segmentActiveStroke(palette) : null,
    // Active segments wear a 1.5px halo so the live edge of the
    // timeline stays glanceable against grid + segment fills.
    strokeWidth: entry.isActive ? 1.5 : 0,
    texture,
    textureColor: segmentHatchStroke(palette),
    warningStroke: entry.warningSeverity
      ? severityStroke(palette, entry.warningSeverity)
      : null,
    cancelledStrike: lifecycle === "cancelled",
    failedBorder: lifecycle === "failed",
    selection: selected
      ? {
          fill: segmentSelectionFill(palette),
          stroke: segmentSelectionStroke(palette),
        }
      : null,
    replay: entry.replay
      ? {
          fill: segmentReplayFill(palette),
          stroke: segmentReplayStroke(palette),
          focused: entry.replay.focused,
        }
      : null,
  };
  return style;
}

function textureFor(state: TimelineSegmentLifecycleState): SegmentTextureKind {
  switch (state) {
    case "waiting":
    case "sleeping":
    case "blocked":
      return "hatch";
    case "replaying":
      return "dots";
    default:
      return "none";
  }
}

function severityStroke(
  palette: TimelineColorPalette,
  severity: TimelineRowWarningSeverity,
): string {
  return segmentWarningStroke(palette, severity);
}

/** Helper — re-export so callers don't need a separate import for the
 *  cancelled strike color. */
export function cancelStrikeColor(palette: TimelineColorPalette): string {
  return segmentCancelStrike(palette);
}

/** Helper — re-export for the failed-state inner border. */
export function failedBorderColor(palette: TimelineColorPalette): string {
  return segmentFailedBorder(palette);
}
