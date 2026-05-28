/**
 * Helpers that resolve "focus" targets — ranges the controller can
 * pivot to via :meth:`zoomToRange` / :meth:`zoomToFit`.
 *
 * Today the resolvers are tiny — they wrap a few range computations
 * the toolbar + keyboard shortcuts share. Tomorrow they'll grow
 * inspector-specific resolvers (debugger active frame, profiler hot
 * span, distributed-trace request).
 */

export interface FocusRange {
  startSeconds: number;
  endSeconds: number;
}

/** Pure: pad a range by ``paddingFraction`` on each side. Used to
 *  keep the focused range from sitting flush against the viewport
 *  edges. */
export function padRange(range: FocusRange, paddingFraction: number): FocusRange {
  const duration = Math.max(0, range.endSeconds - range.startSeconds);
  if (duration === 0) return range;
  const pad = duration * Math.max(0, paddingFraction);
  return {
    startSeconds: range.startSeconds - pad,
    endSeconds: range.endSeconds + pad,
  };
}

/** Pure: merge a list of ranges into the smallest enclosing range. */
export function mergeRanges(ranges: readonly FocusRange[]): FocusRange | null {
  if (ranges.length === 0) return null;
  let start = Number.POSITIVE_INFINITY;
  let end = Number.NEGATIVE_INFINITY;
  for (const range of ranges) {
    if (range.startSeconds < start) start = range.startSeconds;
    if (range.endSeconds > end) end = range.endSeconds;
  }
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return { startSeconds: start, endSeconds: end };
}

/** Pure: ``true`` when a range is non-empty + finite. */
export function isUsableRange(range: FocusRange | null | undefined): range is FocusRange {
  if (!range) return false;
  return (
    Number.isFinite(range.startSeconds) &&
    Number.isFinite(range.endSeconds) &&
    range.endSeconds > range.startSeconds
  );
}
