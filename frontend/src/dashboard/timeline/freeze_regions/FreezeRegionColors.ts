/**
 * Color tokens used by :class:`FreezeRegionRenderer`.
 *
 * The renderer never reads CSS variables — the timeline canvas owns
 * its own palette for the same reason
 * :data:`DEFAULT_TIMELINE_PALETTE` does: per-frame ``getComputedStyle``
 * calls are too expensive.
 *
 * Every entry is an ``rgba(...)`` so the renderer can blend overlays
 * onto the segments without composite-mode juggling. Alpha values are
 * intentionally low for the body (overlay shouldn't drown the
 * underlying segments) and higher for the borders + markers.
 */

import type { FreezeRegionIntent } from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";

export interface FreezeRegionPalette {
  /** Fill applied across the freeze body for ACTIVE regions. */
  activeFill: Record<FreezeRegionIntent, string>;
  /** Fill applied for RECOVERED regions (dimmed). */
  recoveredFill: Record<FreezeRegionIntent, string>;
  /** Stroke applied along the freeze border. */
  border: Record<FreezeRegionIntent, string>;
  /** Stroke applied for the start / end markers. */
  marker: Record<FreezeRegionIntent, string>;
  /** Stroke applied for escalation markers (peak boundary). */
  escalationMarker: string;
  /** Fill applied to a freeze when it is the selected one. */
  selectionFill: string;
  /** Stroke applied to the selected freeze's border. */
  selectionStroke: string;
  /** Stroke applied to the hovered freeze's border. */
  hoverStroke: string;
}

export const DEFAULT_FREEZE_REGION_PALETTE: FreezeRegionPalette = {
  activeFill: {
    warning: "rgba(250,204,21,0.18)",
    critical: "rgba(248,113,113,0.22)",
    freeze: "rgba(248,113,113,0.32)",
    resolved: "rgba(125,130,140,0.08)",
  },
  recoveredFill: {
    warning: "rgba(250,204,21,0.08)",
    critical: "rgba(248,113,113,0.08)",
    freeze: "rgba(248,113,113,0.10)",
    resolved: "rgba(125,130,140,0.06)",
  },
  border: {
    warning: "rgba(250,204,21,0.65)",
    critical: "rgba(248,113,113,0.80)",
    freeze: "rgba(248,113,113,1.00)",
    resolved: "rgba(125,130,140,0.55)",
  },
  marker: {
    warning: "rgba(250,204,21,0.95)",
    critical: "rgba(248,113,113,1.00)",
    freeze: "rgba(248,113,113,1.00)",
    resolved: "rgba(125,130,140,0.80)",
  },
  escalationMarker: "rgba(96,165,250,0.95)",
  selectionFill: "rgba(96,165,250,0.20)",
  selectionStroke: "rgba(96,165,250,1.00)",
  hoverStroke: "rgba(214,217,224,0.85)",
};

/** Pure: pick the body fill for ``(intent, lifecycle)``. */
export function freezeBodyFill(
  palette: FreezeRegionPalette,
  intent: FreezeRegionIntent,
  lifecycle: "active" | "recovered",
): string {
  return lifecycle === "active" ? palette.activeFill[intent] : palette.recoveredFill[intent];
}
