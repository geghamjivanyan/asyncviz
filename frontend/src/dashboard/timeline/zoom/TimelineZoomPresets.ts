/**
 * Pure helpers + builders for zoom presets.
 *
 * A preset is a labeled ``[start, end]`` range the controller can
 * pivot to with a single call. Today the controller ships the
 * always-available "fit all" + "fit default" presets; future
 * inspectors (debugger, profiler) plug in their own via
 * :func:`makePreset`.
 */

import type {
  ZoomPreset,
  ZoomPresetKind,
} from "@/dashboard/timeline/zoom/models/TimelineZoomModels";

export interface PresetSourceContext {
  /** Range covered by every dataset segment + task. */
  dataRange: { startSeconds: number; endSeconds: number } | null;
  /** Range covered by the active replay window (if any). */
  replayRange?: { startSeconds: number; endSeconds: number } | null;
  /** Range covered by the most recent active-segment burst. */
  activeRange?: { startSeconds: number; endSeconds: number } | null;
  /** Range covered by the user-selected task. */
  selectionRange?: { startSeconds: number; endSeconds: number } | null;
  /** Default "home" range — used when no data is loaded. */
  defaultRange?: { startSeconds: number; endSeconds: number };
}

/** Pure: build a preset from raw bounds. */
export function makePreset(
  kind: ZoomPresetKind,
  startSeconds: number,
  endSeconds: number,
  label?: string,
): ZoomPreset {
  if (!(endSeconds > startSeconds)) {
    return {
      kind,
      startSeconds,
      endSeconds: startSeconds + 1,
      label,
    };
  }
  return { kind, startSeconds, endSeconds, label };
}

/** Pure: resolve every available preset for the current context. */
export function resolvePresets(context: PresetSourceContext): ZoomPreset[] {
  const out: ZoomPreset[] = [];
  if (context.dataRange) {
    out.push(
      makePreset(
        "fit-all",
        context.dataRange.startSeconds,
        context.dataRange.endSeconds,
        "Fit all",
      ),
    );
  }
  if (context.selectionRange) {
    out.push(
      makePreset(
        "fit-selection",
        context.selectionRange.startSeconds,
        context.selectionRange.endSeconds,
        "Fit selection",
      ),
    );
  }
  if (context.activeRange) {
    out.push(
      makePreset(
        "fit-active",
        context.activeRange.startSeconds,
        context.activeRange.endSeconds,
        "Fit active tasks",
      ),
    );
  }
  if (context.replayRange) {
    out.push(
      makePreset(
        "fit-replay",
        context.replayRange.startSeconds,
        context.replayRange.endSeconds,
        "Fit replay window",
      ),
    );
  }
  if (context.defaultRange) {
    out.push(
      makePreset(
        "fit-default",
        context.defaultRange.startSeconds,
        context.defaultRange.endSeconds,
        "Reset",
      ),
    );
  }
  return out;
}

/** Pure: find a preset by kind. */
export function findPreset(
  presets: readonly ZoomPreset[],
  kind: ZoomPresetKind,
): ZoomPreset | null {
  return presets.find((preset) => preset.kind === kind) ?? null;
}
