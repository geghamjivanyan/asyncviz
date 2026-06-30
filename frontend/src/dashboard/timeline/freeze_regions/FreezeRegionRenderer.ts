/**
 * Canonical canvas layer that draws runtime freeze regions on top of
 * the timeline.
 *
 * The layer is fundamentally a thin adapter: each frame it takes the
 * latest list of :type:`FreezeRegionView` objects from its source,
 * culls to the visible window, resolves styles, and paints the body +
 * markers. The full draw is replay-deterministic (modulo the
 * intentional pulse animation, which can be disabled via reduced
 * motion).
 *
 * The layer does NOT own freeze-region data — it pulls from a
 * caller-supplied source so React lifecycle owns the projection
 * memoization. Selection / hover / reveal state likewise comes from
 * the caller.
 */

import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";
import type { FreezeRegionView } from "@/dashboard/timeline/freeze_regions/models/FreezeRegionModels";
import type { FreezeRegionPalette } from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";
import { DEFAULT_FREEZE_REGION_PALETTE } from "@/dashboard/timeline/freeze_regions/FreezeRegionColors";
import {
  cullVisibleFreezeRegions,
  snapMarkerX,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionGeometry";
import {
  drawEscalationMarkers,
  drawFreezeEdgeMarkers,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionMarkers";
import { resolveBodyStyle } from "@/dashboard/timeline/freeze_regions/FreezeRegionStyling";
import { makePulseFn } from "@/dashboard/timeline/freeze_regions/FreezeRegionAnimations";
import {
  clampFreezeRegions,
  DEFAULT_VISIBLE_FREEZE_CAP,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionVirtualization";
import type { FreezeHitTestEntry } from "@/dashboard/timeline/freeze_regions/FreezeRegionHitTesting";
import { getFreezeRegionMetrics } from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionMetricsCollector";
import { recordFreezeRegionTrace } from "@/dashboard/timeline/freeze_regions/diagnostics/FreezeRegionTracing";
import type { BlockingEscalationEntry } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

export interface FreezeRegionSource {
  getRegions(): readonly FreezeRegionView[];
  /** Escalation history for a freeze; ``[]`` when unknown. */
  getEscalations?(groupId: string): readonly BlockingEscalationEntry[];
  getSelectedGroupId(): string | null;
  getHoveredGroupId(): string | null;
  getRevealedGroupId?(): string | null;
  isReducedMotion(): boolean;
  /** Optional cap; default :data:`DEFAULT_VISIBLE_FREEZE_CAP`. */
  getVisibleCap?(): number;
}

export interface FreezeRegionRendererOptions {
  id?: string;
  order?: number;
  enabled?: boolean;
  palette?: FreezeRegionPalette;
  /** Callback fired with the visible entries after each frame — used
   *  by the host to keep the hit-test index + screen-reader summary
   *  in sync. */
  onVisibleEntries?: (entries: readonly FreezeHitTestEntry[], hidden: number) => void;
  /** Test seam — overrides ``performance.now``. */
  clock?: () => number;
}

export class FreezeRegionRenderer implements TimelineLayer {
  readonly id: string;
  readonly order: number;
  enabled: boolean;
  private source: FreezeRegionSource | null = null;
  private palette: FreezeRegionPalette;
  private onVisibleEntries: FreezeRegionRendererOptions["onVisibleEntries"];
  private clock: () => number;

  constructor(options: FreezeRegionRendererOptions = {}) {
    this.id = options.id ?? "freeze-regions";
    // Draw above selection (20) but below the cursor overlay (30) so
    // the cursor / tick line stays readable on top of a freeze body.
    this.order = options.order ?? 25;
    this.enabled = options.enabled ?? true;
    this.palette = options.palette ?? DEFAULT_FREEZE_REGION_PALETTE;
    this.onVisibleEntries = options.onVisibleEntries;
    this.clock =
      options.clock ??
      (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  }

  setSource(source: FreezeRegionSource | null): void {
    this.source = source;
  }

  setPalette(palette: FreezeRegionPalette): void {
    this.palette = palette;
  }

  setOnVisibleEntries(handler: FreezeRegionRendererOptions["onVisibleEntries"]): void {
    this.onVisibleEntries = handler;
  }

  render({ ctx, coords }: RenderContext): void {
    if (!this.enabled) return;
    if (this.source === null) return;

    const frameStart = this.clock();
    const allRegions = this.source.getRegions();
    if (allRegions.length === 0) {
      this.onVisibleEntries?.([], 0);
      getFreezeRegionMetrics().recordFrame({
        durationMs: this.clock() - frameStart,
        visibleCount: 0,
        hiddenCount: 0,
        culledCount: 0,
      });
      return;
    }

    const cap = this.source.getVisibleCap?.() ?? DEFAULT_VISIBLE_FREEZE_CAP;
    const { visible: cappedRegions, hidden } = clampFreezeRegions(allRegions, cap);
    const visibleEntries = cullVisibleFreezeRegions(cappedRegions, coords);
    const culledCount = cappedRegions.length - visibleEntries.length;

    const topY = 0;
    const bottomY = coords.viewport.cssHeight;
    const selectedGroupId = this.source.getSelectedGroupId();
    const hoveredGroupId = this.source.getHoveredGroupId();
    const revealedGroupId = this.source.getRevealedGroupId?.() ?? null;
    const reducedMotion = this.source.isReducedMotion();
    const pulseFn = makePulseFn(reducedMotion);
    const nowMs = this.clock();

    ctx.save();
    for (const entry of visibleEntries) {
      const { region, geometry } = entry;
      const style = resolveBodyStyle(region, this.palette, selectedGroupId, hoveredGroupId);
      const isRevealed = region.groupId === revealedGroupId;

      // Body fill (with pulse).
      const pulse = pulseFn(style.pulse, nowMs);
      ctx.globalAlpha = clampAlpha(pulse);
      ctx.fillStyle = style.fill;
      ctx.fillRect(geometry.xStart, topY, geometry.width, bottomY - topY);
      ctx.globalAlpha = 1;

      // Border (single half-pixel rectangle).
      ctx.strokeStyle = style.border;
      ctx.lineWidth = region.groupId === selectedGroupId || isRevealed ? 2 : 1;
      const borderX = snapMarkerX(geometry.xStart);
      const borderRight = snapMarkerX(geometry.xEnd);
      const borderWidth = Math.max(0.5, borderRight - borderX);
      ctx.strokeRect(borderX, topY + 0.5, borderWidth, bottomY - topY - 1);

      // Edge markers (start / end) — drawn after the border so they
      // remain visible at clipped edges.
      drawFreezeEdgeMarkers({
        ctx,
        geometry,
        region,
        palette: this.palette,
        topY,
        bottomY,
      });

      // Escalation markers (when the source can provide them).
      const escalations = this.source.getEscalations?.(region.groupId) ?? [];
      if (escalations.length > 0) {
        drawEscalationMarkers({
          ctx,
          region,
          escalations,
          coords,
          palette: this.palette,
          topY,
          bottomY,
        });
      }
    }
    ctx.restore();

    this.onVisibleEntries?.(visibleEntries, hidden);

    const frameEnd = this.clock();
    getFreezeRegionMetrics().recordFrame({
      durationMs: frameEnd - frameStart,
      visibleCount: visibleEntries.length,
      hiddenCount: hidden,
      culledCount,
    });
    recordFreezeRegionTrace({
      kind: "frame",
      detail: `visible=${visibleEntries.length} hidden=${hidden} culled=${culledCount}`,
    });
  }
}

function clampAlpha(value: number): number {
  if (!Number.isFinite(value)) return 1;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}
