/**
 * Lightweight cap-and-trim helpers for warning lists.
 *
 * The emitter's recent-ring is bounded (default 64). Active groups
 * are unbounded in principle but real-world freezes cap at a handful
 * concurrently. Real virtualization (DOM recycling) isn't justified
 * at these scales; we just truncate to a configurable visible cap +
 * report how many were hidden so the panel can show "show all".
 *
 * Exporting the cap from one place keeps the panel + tests in sync
 * without scattering magic numbers.
 */

import type { BlockingWarningView } from "@/dashboard/warnings/blocking/models/BlockingWarningModels";

export const DEFAULT_ACTIVE_VISIBLE_CAP = 32;
export const DEFAULT_RECENT_VISIBLE_CAP = 16;

export interface VirtualizationResult {
  visible: readonly BlockingWarningView[];
  hidden: number;
}

/**
 * Return the first ``cap`` views + the count that were clipped.
 *
 * Defensive: a negative or non-finite cap yields the full list.
 */
export function clampViews(
  views: readonly BlockingWarningView[],
  cap: number,
): VirtualizationResult {
  if (!Number.isFinite(cap) || cap <= 0 || views.length <= cap) {
    return { visible: views, hidden: 0 };
  }
  return { visible: views.slice(0, cap), hidden: views.length - cap };
}
