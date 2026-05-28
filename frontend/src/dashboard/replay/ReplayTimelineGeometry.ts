/**
 * Pure geometry helpers for the replay timeline.
 *
 * Every coordinate translation between *sequence space* and *pixel
 * space* lives in this file so the components, scrubber, marker
 * renderer, and tests all share one implementation. Keeping it pure
 * means the same math is testable headlessly without spinning up
 * the DOM.
 */

import type {
  ReplaySessionWindow,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

/** Clamp ``v`` to ``[low, high]``. ``NaN`` collapses to ``low``. */
export function clamp(value: number, low: number, high: number): number {
  if (Number.isNaN(value)) return low;
  if (value < low) return low;
  if (value > high) return high;
  return value;
}

/**
 * Map a sequence to its horizontal pixel offset inside ``widthPx``.
 *
 * Returns ``0`` for an empty viewport / window so callers don't need
 * a separate guard; the corresponding marker simply lands at the
 * left edge until the recording has any frames at all.
 */
export function sequenceToPixel(
  sequence: number,
  viewport: ReplayTimelineViewport,
): number {
  const span = viewport.endSequence - viewport.startSequence;
  if (span <= 0 || viewport.widthPx <= 0) return 0;
  const clamped = clamp(sequence, viewport.startSequence, viewport.endSequence);
  const fraction = (clamped - viewport.startSequence) / span;
  return fraction * viewport.widthPx;
}

/** Inverse of :func:`sequenceToPixel` — clamped at viewport edges. */
export function pixelToSequence(
  pixel: number,
  viewport: ReplayTimelineViewport,
): number {
  if (viewport.widthPx <= 0) return viewport.startSequence;
  const clamped = clamp(pixel, 0, viewport.widthPx);
  const fraction = clamped / viewport.widthPx;
  const span = viewport.endSequence - viewport.startSequence;
  return Math.round(viewport.startSequence + fraction * span);
}

/**
 * Normalize a sequence onto ``[0, 1]`` relative to the *whole window*
 * (not the current viewport). Mini-map + accessibility text use this
 * so the value is independent of scroll position.
 */
export function sequenceToFraction(
  sequence: number,
  window: ReplaySessionWindow,
): number {
  const span = window.maxSequence - window.minSequence;
  if (span <= 0) return 0;
  const clamped = clamp(sequence, window.minSequence, window.maxSequence);
  return (clamped - window.minSequence) / span;
}

/** Inverse of :func:`sequenceToFraction`. */
export function fractionToSequence(
  fraction: number,
  window: ReplaySessionWindow,
): number {
  const clamped = clamp(fraction, 0, 1);
  const span = window.maxSequence - window.minSequence;
  return Math.round(window.minSequence + clamped * span);
}

/**
 * Map a ``monotonic_ns`` timestamp to a sequence. The mapping isn't
 * exact (sequence space + timestamp space evolve independently in
 * the recorder), but for UX purposes a linear interpolation over the
 * window's spans is good enough — and consistent.
 */
export function timestampToSequence(
  monotonicNs: number,
  window: ReplaySessionWindow,
): number {
  const tsSpan = window.maxMonotonicNs - window.minMonotonicNs;
  if (tsSpan <= 0) return window.minSequence;
  const clamped = clamp(
    monotonicNs,
    window.minMonotonicNs,
    window.maxMonotonicNs,
  );
  const fraction = (clamped - window.minMonotonicNs) / tsSpan;
  const seqSpan = window.maxSequence - window.minSequence;
  return Math.round(window.minSequence + fraction * seqSpan);
}

/** Inverse of :func:`timestampToSequence`. */
export function sequenceToTimestamp(
  sequence: number,
  window: ReplaySessionWindow,
): number {
  const seqSpan = window.maxSequence - window.minSequence;
  if (seqSpan <= 0) return window.minMonotonicNs;
  const clamped = clamp(sequence, window.minSequence, window.maxSequence);
  const fraction = (clamped - window.minSequence) / seqSpan;
  const tsSpan = window.maxMonotonicNs - window.minMonotonicNs;
  return Math.round(window.minMonotonicNs + fraction * tsSpan);
}

/**
 * Decide whether a sequence is currently visible in the viewport.
 * Used by the marker renderer to skip off-screen markers.
 */
export function sequenceInViewport(
  sequence: number,
  viewport: ReplayTimelineViewport,
): boolean {
  return (
    sequence >= viewport.startSequence && sequence <= viewport.endSequence
  );
}

/** Build a viewport that spans the whole window. */
export function viewportForWindow(
  window: ReplaySessionWindow,
  widthPx: number,
): ReplayTimelineViewport {
  return {
    startSequence: window.minSequence,
    endSequence: Math.max(window.minSequence, window.maxSequence),
    widthPx,
  };
}
