/**
 * Render-time integrity checks.
 *
 * Cheap invariants that a developer build can flip on to catch
 * regressions. Each check returns a structured violation rather than
 * throwing — the pipeline records the violation, surfaces it through
 * tracing, and continues rendering. We never crash the canvas because
 * an invariant tripped.
 */

import type { DirtyRegion } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import { isFullRegion } from "@/dashboard/timeline/rendering_optimization/models/dirty_region";
import type { RenderPass } from "@/dashboard/timeline/rendering_optimization/models/render_pass";

export type IntegrityViolationKind =
  | "negative-region"
  | "non-finite-region"
  | "duplicate-pass-id"
  | "invalid-priority"
  | "redraw-area-exceeds-canvas";

export interface IntegrityViolation {
  readonly kind: IntegrityViolationKind;
  readonly detail: string;
}

export function checkDirtyRegion(region: DirtyRegion): IntegrityViolation | null {
  if (isFullRegion(region)) return null;
  if (!Number.isFinite(region.x) || !Number.isFinite(region.y)) {
    return { kind: "non-finite-region", detail: `(${region.x}, ${region.y})` };
  }
  if (region.width <= 0 || region.height <= 0) {
    return {
      kind: "negative-region",
      detail: `${region.width}x${region.height}`,
    };
  }
  return null;
}

export function checkPasses(passes: readonly RenderPass[]): IntegrityViolation | null {
  const seen = new Set<string>();
  for (const pass of passes) {
    if (seen.has(pass.id)) {
      return { kind: "duplicate-pass-id", detail: pass.id };
    }
    seen.add(pass.id);
    if (!Number.isFinite(pass.priority) || pass.priority < 0) {
      return {
        kind: "invalid-priority",
        detail: `${pass.id}=${pass.priority}`,
      };
    }
  }
  return null;
}

export function checkRedrawArea(
  redrawAreaPx2: number,
  canvasAreaPx2: number,
): IntegrityViolation | null {
  if (!Number.isFinite(redrawAreaPx2) || redrawAreaPx2 < 0) {
    return {
      kind: "non-finite-region",
      detail: `redrawAreaPx2=${redrawAreaPx2}`,
    };
  }
  // Tolerate up to 1.05x canvas (overlap allowed); beyond is a bug.
  if (canvasAreaPx2 > 0 && redrawAreaPx2 > canvasAreaPx2 * 1.05) {
    return {
      kind: "redraw-area-exceeds-canvas",
      detail: `${redrawAreaPx2}px2 > ${canvasAreaPx2}px2`,
    };
  }
  return null;
}
