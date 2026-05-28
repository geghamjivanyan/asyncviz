/**
 * Styling decisions for freeze-region body rendering.
 *
 * The renderer asks ``resolveBodyStyle`` once per visible region to
 * pick its fill + alpha + border. Pulling the logic out keeps the
 * renderer trivial and makes the styling rules unit-testable without
 * a canvas mock.
 */

import type {
  FreezeRegionView,
} from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";
import {
  freezeBodyFill,
  type FreezeRegionPalette,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";

export interface ResolvedFreezeStyle {
  fill: string;
  border: string;
  /** ``true`` when the body should pulse (lightly brighter alpha). */
  pulse: boolean;
}

/**
 * Pick the fill + border + pulse-flag for a freeze region.
 *
 * Pulsing is intentionally a flag rather than animation state —
 * animations land in :class:`FreezeRegionAnimations` so the renderer
 * stays declarative.
 */
export function resolveBodyStyle(
  region: FreezeRegionView,
  palette: FreezeRegionPalette,
  selectedGroupId: string | null,
  hoveredGroupId: string | null,
): ResolvedFreezeStyle {
  const isSelected = region.groupId === selectedGroupId;
  const isHovered = region.groupId === hoveredGroupId;
  let border = palette.border[region.intent];
  if (isSelected) border = palette.selectionStroke;
  else if (isHovered) border = palette.hoverStroke;

  const baseFill = freezeBodyFill(palette, region.intent, region.lifecycle);
  const fill = isSelected ? palette.selectionFill : baseFill;
  const pulse = region.lifecycle === "active" && region.state === "active";
  return { fill, border, pulse };
}
