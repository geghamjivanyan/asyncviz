/**
 * Accessibility metadata for the blocking-warning panel.
 *
 * Builders + announcers that keep screen-reader semantics in sync with
 * the visual rendering. Components consume these to compose
 * ``aria-label``s + status messages without scattering string
 * concatenation logic across the tree.
 *
 * No DOM access here — these are pure builders. The panel wires them
 * into ``aria-label`` / ``aria-live`` attributes.
 */

import type {
  BlockingGroupSeverity,
  BlockingGroupState,
  BlockingWarningView,
} from "@/dashboard/warnings/blocking/models/BlockingWarningModels";
import { formatDurationMs, formatLagMs } from "@/dashboard/warnings/blocking/utils/formatting";

const STATE_LABEL: Record<BlockingGroupState, string> = {
  opened: "opened",
  escalating: "escalating",
  active: "active",
  recovered: "recovered",
  expired: "expired",
};

const SEVERITY_LABEL: Record<BlockingGroupSeverity, string> = {
  NONE: "normal",
  WARNING: "warning",
  CRITICAL: "critical",
  FREEZE: "freeze",
};

/** One-line accessible label for a warning card. */
export function describeViewForAccessibility(view: BlockingWarningView): string {
  const parts: string[] = [];
  parts.push(`${SEVERITY_LABEL[view.severity]} ${STATE_LABEL[view.state]} blocking warning`);
  if (view.windowId !== null) parts.push(`window ${view.windowId}`);
  parts.push(`duration ${formatDurationMs(view.freezeDurationMs)}`);
  parts.push(`peak lag ${formatLagMs(view.peakLagMs)}`);
  if (view.captureIds.length > 0) {
    parts.push(
      `${view.captureIds.length} correlated capture${view.captureIds.length === 1 ? "" : "s"}`,
    );
  }
  if (view.peakSeverity !== view.severity) {
    parts.push(`peak severity ${SEVERITY_LABEL[view.peakSeverity]}`);
  }
  if (view.taskName !== null) {
    parts.push(`task ${view.taskName}`);
  }
  return parts.join(", ");
}

/** Live announcement for the panel: counts + last-event note. */
export function describeCountsAnnouncement(
  active: number,
  recent: number,
  filtered: boolean,
): string {
  if (active === 0 && recent === 0) {
    return filtered
      ? "No blocking warnings match the current filter."
      : "No blocking warnings recorded.";
  }
  const segments: string[] = [];
  segments.push(`${active} active blocking warning${active === 1 ? "" : "s"}`);
  segments.push(`${recent} recent`);
  if (filtered) segments.push("filtered view");
  return segments.join(", ");
}

/** Polite announcement for a new transition. */
export function describeTransitionAnnouncement(view: BlockingWarningView): string {
  return `Blocking ${STATE_LABEL[view.state]} (${SEVERITY_LABEL[view.severity]}) on window ${view.windowId ?? "<none>"}`;
}
