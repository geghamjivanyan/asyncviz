/**
 * Incremental renderer.
 *
 * Given a set of dirty regions + a pipeline of render passes, the
 * incremental renderer decides which subset of the canvas needs to be
 * cleared + which passes need to re-paint. Two paths:
 *
 *   * **incremental** — we clip to the dirty regions + replay only
 *     the passes that overlap them.
 *   * **full**        — the dirty set collapsed to "full", or the
 *     viewport changed: clear + replay every pass.
 *
 * The renderer is *framework-free*: it operates on a
 * ``CanvasRenderingContext2D`` and a callback per pass. The pipeline
 * supplies both.
 */

import {
  isFullRegion,
  type DirtyRegion,
} from "@/dashboard/timeline/rendering_optimization/models/dirty_region";

export type PassDrawer = (region: DirtyRegion | null) => void;

export interface IncrementalRenderInputs {
  readonly ctx: CanvasRenderingContext2D;
  readonly cssWidth: number;
  readonly cssHeight: number;
  readonly regions: readonly DirtyRegion[];
  readonly passes: readonly { id: string; draw: PassDrawer }[];
}

export interface IncrementalRenderResult {
  readonly mode: "incremental" | "full" | "skip";
  readonly regionsRedrawn: number;
  readonly passesExecuted: number;
  readonly areaPx2: number;
  readonly failures: number;
}

export class TimelineIncrementalRenderer {
  /** Execute one redraw cycle. */
  run(inputs: IncrementalRenderInputs): IncrementalRenderResult {
    const { ctx, cssWidth, cssHeight, regions, passes } = inputs;
    if (regions.length === 0 || passes.length === 0) {
      return {
        mode: "skip",
        regionsRedrawn: 0,
        passesExecuted: 0,
        areaPx2: 0,
        failures: 0,
      };
    }

    const fullRedraw = regions.some(isFullRegion);
    if (fullRedraw) {
      return this.runFull(ctx, cssWidth, cssHeight, passes);
    }

    let regionsRedrawn = 0;
    let passesExecuted = 0;
    let areaPx2 = 0;
    let failures = 0;

    for (const region of regions) {
      const clamped = clampRegion(region, cssWidth, cssHeight);
      if (clamped === null) continue;
      regionsRedrawn += 1;
      areaPx2 += clamped.width * clamped.height;
      ctx.save();
      try {
        beginRegionClip(ctx, clamped);
        ctx.clearRect(clamped.x, clamped.y, clamped.width, clamped.height);
        for (const pass of passes) {
          try {
            pass.draw(region);
            passesExecuted += 1;
          } catch {
            failures += 1;
          }
        }
      } finally {
        ctx.restore();
      }
    }

    return {
      mode: "incremental",
      regionsRedrawn,
      passesExecuted,
      areaPx2,
      failures,
    };
  }

  private runFull(
    ctx: CanvasRenderingContext2D,
    cssWidth: number,
    cssHeight: number,
    passes: readonly { id: string; draw: PassDrawer }[],
  ): IncrementalRenderResult {
    let passesExecuted = 0;
    let failures = 0;
    ctx.save();
    try {
      ctx.clearRect(0, 0, cssWidth, cssHeight);
      for (const pass of passes) {
        try {
          pass.draw(null);
          passesExecuted += 1;
        } catch {
          failures += 1;
        }
      }
    } finally {
      ctx.restore();
    }
    return {
      mode: "full",
      regionsRedrawn: 1,
      passesExecuted,
      areaPx2: cssWidth * cssHeight,
      failures,
    };
  }
}

function beginRegionClip(ctx: CanvasRenderingContext2D, region: DirtyRegion): void {
  ctx.beginPath();
  ctx.rect(region.x, region.y, region.width, region.height);
  ctx.clip();
}

function clampRegion(
  region: DirtyRegion,
  cssWidth: number,
  cssHeight: number,
): DirtyRegion | null {
  const x = Math.max(0, region.x);
  const y = Math.max(0, region.y);
  const right = Math.min(cssWidth, region.x + region.width);
  const bottom = Math.min(cssHeight, region.y + region.height);
  const width = right - x;
  const height = bottom - y;
  if (width <= 0 || height <= 0) return null;
  return { ...region, x, y, width, height };
}
