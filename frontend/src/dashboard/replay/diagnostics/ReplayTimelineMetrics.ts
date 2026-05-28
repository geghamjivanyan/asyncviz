/**
 * Module-scoped metrics for the replay timeline controls.
 *
 * Counters track scrub latency, seek timings, render pass cadence,
 * marker counts, and rerender frequency. The diagnostics page reads
 * a snapshot via :func:`getReplayTimelineMetricsSnapshot` so it can
 * surface UX-side health without the dashboard having to poll.
 */

export interface ReplayTimelineMetricsSnapshot {
  scrubStarts: number;
  scrubEnds: number;
  scrubUpdates: number;
  seeksRequested: number;
  seekChangesObserved: number;
  cumulativeSeekLatencyMs: number;
  maxSeekLatencyMs: number;
  markerRenderPasses: number;
  bucketRenderPasses: number;
  keyboardEvents: number;
  focusChanges: number;
  bookmarksAdded: number;
  bookmarksRemoved: number;
}

const initial = (): ReplayTimelineMetricsSnapshot => ({
  scrubStarts: 0,
  scrubEnds: 0,
  scrubUpdates: 0,
  seeksRequested: 0,
  seekChangesObserved: 0,
  cumulativeSeekLatencyMs: 0,
  maxSeekLatencyMs: 0,
  markerRenderPasses: 0,
  bucketRenderPasses: 0,
  keyboardEvents: 0,
  focusChanges: 0,
  bookmarksAdded: 0,
  bookmarksRemoved: 0,
});

let metrics: ReplayTimelineMetricsSnapshot = initial();

export function recordScrubStart(): void {
  metrics = { ...metrics, scrubStarts: metrics.scrubStarts + 1 };
}

export function recordScrubEnd(): void {
  metrics = { ...metrics, scrubEnds: metrics.scrubEnds + 1 };
}

export function recordScrubUpdate(): void {
  metrics = { ...metrics, scrubUpdates: metrics.scrubUpdates + 1 };
}

export function recordSeekRequested(): void {
  metrics = { ...metrics, seeksRequested: metrics.seeksRequested + 1 };
}

export function recordSeekChange(latencyMs: number): void {
  const max = Math.max(metrics.maxSeekLatencyMs, latencyMs);
  metrics = {
    ...metrics,
    seekChangesObserved: metrics.seekChangesObserved + 1,
    cumulativeSeekLatencyMs: metrics.cumulativeSeekLatencyMs + latencyMs,
    maxSeekLatencyMs: max,
  };
}

export function recordMarkerRenderPass(): void {
  metrics = { ...metrics, markerRenderPasses: metrics.markerRenderPasses + 1 };
}

export function recordBucketRenderPass(): void {
  metrics = { ...metrics, bucketRenderPasses: metrics.bucketRenderPasses + 1 };
}

export function recordKeyboardEvent(): void {
  metrics = { ...metrics, keyboardEvents: metrics.keyboardEvents + 1 };
}

export function recordFocusChange(): void {
  metrics = { ...metrics, focusChanges: metrics.focusChanges + 1 };
}

export function recordBookmarkAdded(): void {
  metrics = { ...metrics, bookmarksAdded: metrics.bookmarksAdded + 1 };
}

export function recordBookmarkRemoved(): void {
  metrics = { ...metrics, bookmarksRemoved: metrics.bookmarksRemoved + 1 };
}

export function getReplayTimelineMetricsSnapshot(): ReplayTimelineMetricsSnapshot {
  return { ...metrics };
}

export function resetReplayTimelineMetrics(): void {
  metrics = initial();
}
