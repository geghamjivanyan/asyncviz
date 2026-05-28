/**
 * Accessibility metadata builders for the freeze-region layer.
 *
 * The canvas itself is rendering-only; the surrounding container
 * exposes an aria-live region that announces freeze counts +
 * selection changes through these pure helpers.
 */

import type {
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0 s";
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)} ms`;
  if (seconds < 60) return `${seconds.toFixed(2)} s`;
  const m = Math.floor(seconds / 60);
  const s = (seconds - m * 60).toFixed(1);
  return `${m}m ${s}s`;
}

/** One-line announcement for a freeze under the pointer / cursor. */
export function describeFreezeForAccessibility(region: FreezeRegionView): string {
  const parts: string[] = [];
  parts.push(`${region.intent} freeze`);
  if (region.windowId !== null) parts.push(`window ${region.windowId}`);
  parts.push(`duration ${formatSeconds(region.durationSeconds)}`);
  if (region.captureCount > 0) {
    parts.push(
      `${region.captureCount} correlated capture${region.captureCount === 1 ? "" : "s"}`,
    );
  }
  if (region.taskName !== null) parts.push(`task ${region.taskName}`);
  if (region.peakSeverity !== region.severity) {
    parts.push(`peak severity ${region.peakSeverity}`);
  }
  return parts.join(", ");
}

/** Region-summary announcement (live region). */
export function describeFreezeCountsAnnouncement(
  activeCount: number,
  recoveredCount: number,
  visibleCount: number,
): string {
  if (activeCount === 0 && recoveredCount === 0) {
    return "No freeze regions currently rendered on the timeline.";
  }
  const segments: string[] = [];
  segments.push(`${activeCount} active freeze region${activeCount === 1 ? "" : "s"}`);
  if (recoveredCount > 0) segments.push(`${recoveredCount} recovered`);
  segments.push(`${visibleCount} currently visible`);
  return segments.join(", ");
}

/** Announcement when the operator clicks a freeze. */
export function describeFreezeFocusAnnouncement(region: FreezeRegionView): string {
  return `Focused ${region.intent} freeze ${region.windowId ?? "no-window"}, duration ${formatSeconds(region.durationSeconds)}.`;
}
