/**
 * Seek-intent helpers.
 *
 * The store stores *cursor* state; this module converts UI events
 * (click on a position, keyboard arrow, bookmark activate) into a
 * structured :class:`ReplayControlIntent` the engine bridge can
 * dispatch.
 */

import {
  clamp,
  fractionToSequence,
  pixelToSequence,
  sequenceToTimestamp,
} from "@/dashboard/replay/ReplayTimelineGeometry";
import type {
  ReplayBookmark,
  ReplayControlIntent,
  ReplaySessionWindow,
  ReplayTimelineMarker,
  ReplayTimelineViewport,
} from "@/dashboard/replay/models/ReplayTimelineModels";

/** Map a click X coordinate to a seek intent. */
export function seekFromPixel(
  pixelX: number,
  viewport: ReplayTimelineViewport,
): ReplayControlIntent {
  return {
    type: "seek-sequence",
    sequence: pixelToSequence(pixelX, viewport),
  };
}

/** Map a normalized fraction (0..1 across the full window) into a
 *  seek intent — used by the mini-map and keyboard PageUp/PageDown. */
export function seekFromFraction(
  fraction: number,
  window: ReplaySessionWindow,
): ReplayControlIntent {
  return {
    type: "seek-sequence",
    sequence: fractionToSequence(fraction, window),
  };
}

/** Map a marker activation to a seek intent. */
export function seekToMarker(marker: ReplayTimelineMarker): ReplayControlIntent {
  return { type: "seek-sequence", sequence: marker.sequence };
}

/** Map a bookmark activation to a seek intent. */
export function seekToBookmark(bookmark: ReplayBookmark): ReplayControlIntent {
  return { type: "jump-to-bookmark", bookmarkId: bookmark.id };
}

/** Step the cursor by one sequence value, clamped to the window. */
export function stepCursor(
  currentSequence: number,
  delta: number,
  window: ReplaySessionWindow,
): ReplayControlIntent {
  return {
    type: "seek-sequence",
    sequence: clamp(currentSequence + delta, window.minSequence, window.maxSequence),
  };
}

/** Jump by a percentage of the window — used by PageUp/PageDown
 *  and shift-arrow keystrokes. */
export function jumpByFraction(
  currentSequence: number,
  fractionDelta: number,
  window: ReplaySessionWindow,
): ReplayControlIntent {
  const span = window.maxSequence - window.minSequence;
  if (span <= 0) {
    return { type: "seek-sequence", sequence: window.minSequence };
  }
  const delta = Math.round(span * fractionDelta);
  return stepCursor(currentSequence, delta, window);
}

/** Convert a sequence target to its timestamp equivalent for
 *  ``seek-timestamp`` callers (the timeline overlays sometimes
 *  prefer timestamp targets). */
export function seekToTimestampForSequence(
  sequence: number,
  window: ReplaySessionWindow,
): ReplayControlIntent {
  return {
    type: "seek-timestamp",
    monotonicNs: sequenceToTimestamp(sequence, window),
  };
}
