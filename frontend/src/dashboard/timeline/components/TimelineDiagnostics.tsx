/**
 * Inline diagnostics for the canvas timeline renderer.
 *
 * Polls :class:`TimelineRendererMetrics` at 1Hz and renders the
 * snapshot for the diagnostics page.
 */

import { useEffect, useState } from "react";
import { Badge } from "@/ui/primitives/Badge";
import {
  getTimelineRendererMetrics,
  type TimelineRendererMetricsSnapshot,
} from "@/dashboard/timeline/observability";
import { getTimelineRowMetrics, type TimelineRowMetricsSnapshot } from "@/dashboard/timeline/rows";
import {
  getTimelineSegmentMetrics,
  type TimelineSegmentMetricsSnapshot,
} from "@/dashboard/timeline/segments";
import {
  getTimelineLiveMetrics,
  type TimelineLiveMetricsSnapshot,
} from "@/dashboard/timeline/live";
import {
  getTimelineWindowMetrics,
  type TimelineWindowMetricsSnapshot,
} from "@/dashboard/timeline/virtualization";
import {
  getTimelineScaleMetrics,
  type TimelineScaleMetricsSnapshot,
} from "@/dashboard/timeline/scaling";
import {
  getTimelineZoomMetrics,
  type TimelineZoomMetricsSnapshot,
} from "@/dashboard/timeline/zoom";
import { getTimelinePanMetrics, type TimelinePanMetricsSnapshot } from "@/dashboard/timeline/pan";
import {
  getTimelineSelectionMetrics,
  type TimelineSelectionMetricsSnapshot,
} from "@/dashboard/timeline/selection";

const POLL_MS = 1000;

export function TimelineDiagnostics() {
  const [snapshot, setSnapshot] = useState<TimelineRendererMetricsSnapshot>(() =>
    getTimelineRendererMetrics().snapshot(),
  );
  const [rowSnapshot, setRowSnapshot] = useState<TimelineRowMetricsSnapshot>(() =>
    getTimelineRowMetrics().snapshot(),
  );
  const [segmentSnapshot, setSegmentSnapshot] = useState<TimelineSegmentMetricsSnapshot>(() =>
    getTimelineSegmentMetrics().snapshot(),
  );
  const [liveSnapshot, setLiveSnapshot] = useState<TimelineLiveMetricsSnapshot>(() =>
    getTimelineLiveMetrics().snapshot(),
  );
  const [windowSnapshot, setWindowSnapshot] = useState<TimelineWindowMetricsSnapshot>(() =>
    getTimelineWindowMetrics().snapshot(),
  );
  const [scaleSnapshot, setScaleSnapshot] = useState<TimelineScaleMetricsSnapshot>(() =>
    getTimelineScaleMetrics().snapshot(),
  );
  const [zoomSnapshot, setZoomSnapshot] = useState<TimelineZoomMetricsSnapshot>(() =>
    getTimelineZoomMetrics().snapshot(),
  );
  const [panSnapshot, setPanSnapshot] = useState<TimelinePanMetricsSnapshot>(() =>
    getTimelinePanMetrics().snapshot(),
  );
  const [selectionSnapshot, setSelectionSnapshot] = useState<TimelineSelectionMetricsSnapshot>(() =>
    getTimelineSelectionMetrics().snapshot(),
  );
  useEffect(() => {
    const handle = window.setInterval(() => {
      setSnapshot(getTimelineRendererMetrics().snapshot());
      setRowSnapshot(getTimelineRowMetrics().snapshot());
      setSegmentSnapshot(getTimelineSegmentMetrics().snapshot());
      setLiveSnapshot(getTimelineLiveMetrics().snapshot());
      setWindowSnapshot(getTimelineWindowMetrics().snapshot());
      setScaleSnapshot(getTimelineScaleMetrics().snapshot());
      setZoomSnapshot(getTimelineZoomMetrics().snapshot());
      setPanSnapshot(getTimelinePanMetrics().snapshot());
      setSelectionSnapshot(getTimelineSelectionMetrics().snapshot());
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, []);
  return (
    <section
      data-timeline-diagnostics="true"
      aria-label="Timeline renderer diagnostics"
      className="flex flex-col gap-2 p-3 font-mono text-xs text-muted"
    >
      <header className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest text-muted">Timeline renderer</span>
        <Badge intent={snapshot.droppedFrameWarnings > 0 ? "warning" : "default"}>
          {snapshot.droppedFrameWarnings > 0 ? "dropped frames" : "stable"}
        </Badge>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Frames rendered" value={snapshot.framesRendered} />
        <Stat label="Last frame ms" value={snapshot.lastFrameDurationMs.toFixed(2)} />
        <Stat label="Max frame ms" value={snapshot.maxFrameDurationMs.toFixed(2)} />
        <Stat label="Dropped frames" value={snapshot.droppedFrameWarnings} />
        <Stat label="Visible rows total" value={snapshot.visibleRowsTotal} />
        <Stat label="Visible segments total" value={snapshot.visibleSegmentsTotal} />
        <Stat label="Resize events" value={snapshot.resizeEvents} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Invalidations
        </span>
        {Object.entries(snapshot.invalidationsByReason).map(([reason, count]) => (
          <Stat key={reason} label={reason} value={count} />
        ))}
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Row renderer
        </span>
        <Stat label="Rows rendered" value={rowSnapshot.rowsRendered} />
        <Stat label="Visible rows total" value={rowSnapshot.visibleRowsTotal} />
        <Stat label="Labels rendered" value={rowSnapshot.labelsRendered} />
        <Stat label="Labels truncated" value={rowSnapshot.labelsTruncated} />
        <Stat label="Selections rendered" value={rowSnapshot.selectionsRendered} />
        <Stat label="Warnings rendered" value={rowSnapshot.warningsRendered} />
        <Stat label="Hit tests" value={rowSnapshot.hitTestsPerformed} />
        <Stat label="Projections built" value={rowSnapshot.projectionsBuilt} />
        <Stat label="Last row frame ms" value={rowSnapshot.lastFrameMs.toFixed(2)} />
        <Stat label="Max row frame ms" value={rowSnapshot.maxFrameMs.toFixed(2)} />
        <Stat label="Row dropped frames" value={rowSnapshot.droppedFrameWarnings} />
        <Stat label="Text cache hits" value={rowSnapshot.textCacheHits} />
        <Stat label="Text cache misses" value={rowSnapshot.textCacheMisses} />
        <Stat label="Replay marked frames" value={rowSnapshot.replayMarkedFrames} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Segment renderer
        </span>
        <Stat label="Segments rendered" value={segmentSnapshot.segmentsRendered} />
        <Stat label="Visible segments total" value={segmentSnapshot.visibleSegmentsTotal} />
        <Stat label="Segments culled" value={segmentSnapshot.segmentsCulled} />
        <Stat label="Warnings rendered" value={segmentSnapshot.warningsRendered} />
        <Stat label="Selections rendered" value={segmentSnapshot.selectionsRendered} />
        <Stat label="Decorators rendered" value={segmentSnapshot.decoratorsRendered} />
        <Stat label="Hit tests" value={segmentSnapshot.hitTestsPerformed} />
        <Stat label="Geometry hits" value={segmentSnapshot.geometryCacheHits} />
        <Stat label="Geometry misses" value={segmentSnapshot.geometryCacheMisses} />
        <Stat label="Geometry evictions" value={segmentSnapshot.geometryCacheEvictions} />
        <Stat label="Overlaps observed" value={segmentSnapshot.overlapsObserved} />
        <Stat label="Active segment frames" value={segmentSnapshot.activeSegmentFrames} />
        <Stat label="Replay marked frames" value={segmentSnapshot.replayMarkedFrames} />
        <Stat label="Last segment frame ms" value={segmentSnapshot.lastFrameMs.toFixed(2)} />
        <Stat label="Max segment frame ms" value={segmentSnapshot.maxFrameMs.toFixed(2)} />
        <Stat label="Segment dropped frames" value={segmentSnapshot.droppedFrameWarnings} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Live engine
        </span>
        <Stat label="Mode" value={liveSnapshot.currentMode} />
        <Stat label="Envelopes observed" value={liveSnapshot.envelopesObserved} />
        <Stat label="Envelopes suppressed" value={liveSnapshot.envelopesSuppressed} />
        <Stat label="Live envelopes applied" value={liveSnapshot.liveEnvelopesApplied} />
        <Stat label="Replay batches" value={liveSnapshot.replayBatchesApplied} />
        <Stat label="Replay envelopes" value={liveSnapshot.replayEnvelopesApplied} />
        <Stat label="Batches emitted" value={liveSnapshot.batchesEmitted} />
        <Stat label="Regions coalesced" value={liveSnapshot.batchRegionsCoalesced} />
        <Stat label="Flushes scheduled" value={liveSnapshot.flushesScheduled} />
        <Stat label="Flushes executed" value={liveSnapshot.flushesExecuted} />
        <Stat label="Flushes skipped (idle)" value={liveSnapshot.flushesSkippedIdle} />
        <Stat label="Active ticks" value={liveSnapshot.activeTicks} />
        <Stat label="Active ticks suppressed" value={liveSnapshot.activeTicksSuppressed} />
        <Stat label="Last batch latency ms" value={liveSnapshot.lastBatchLatencyMs.toFixed(2)} />
        <Stat label="Max batch latency ms" value={liveSnapshot.maxBatchLatencyMs.toFixed(2)} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Virtualization
        </span>
        <Stat label="Window resolutions" value={windowSnapshot.windowResolutions} />
        <Stat label="Window cache hits" value={windowSnapshot.windowCacheHits} />
        <Stat label="Row culls" value={windowSnapshot.rowCulls} />
        <Stat label="Visible rows total" value={windowSnapshot.visibleRowsTotal} />
        <Stat label="Rows culled total" value={windowSnapshot.rowsCulledTotal} />
        <Stat label="Segment culls" value={windowSnapshot.segmentCulls} />
        <Stat label="Visible segs total" value={windowSnapshot.visibleSegmentsTotal} />
        <Stat label="Segs culled total" value={windowSnapshot.segmentsCulledTotal} />
        <Stat label="Frame cache hits" value={windowSnapshot.cacheHits} />
        <Stat label="Frame cache misses" value={windowSnapshot.cacheMisses} />
        <Stat label="Frame cache evictions" value={windowSnapshot.cacheEvictions} />
        <Stat label="Spatial index builds" value={windowSnapshot.indexBuilds} />
        <Stat label="Spatial queries" value={windowSnapshot.spatialQueries} />
        <Stat label="Spatial lookups" value={windowSnapshot.spatialLookups} />
        <Stat label="Last recalc ms" value={windowSnapshot.lastRecalculationMs.toFixed(2)} />
        <Stat label="Max recalc ms" value={windowSnapshot.maxRecalculationMs.toFixed(2)} />
        <Stat label="Recalcs over budget" value={windowSnapshot.recalculationsOverBudget} />
        <Stat label="Invalidations observed" value={windowSnapshot.invalidationsObserved} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Time scale
        </span>
        <Stat label="Scale changes" value={scaleSnapshot.scaleChanges} />
        <Stat label="Zooms" value={scaleSnapshot.scaleZooms} />
        <Stat label="Pans" value={scaleSnapshot.scalePans} />
        <Stat label="Fits" value={scaleSnapshot.scaleFits} />
        <Stat label="Viewport normalizations" value={scaleSnapshot.viewportNormalizations} />
        <Stat label="Precision warnings" value={scaleSnapshot.precisionWarnings} />
        <Stat label="Min-constraint hits" value={scaleSnapshot.constraintHitsMin} />
        <Stat label="Max-constraint hits" value={scaleSnapshot.constraintHitsMax} />
        <Stat label="Ticks generated" value={scaleSnapshot.ticksGenerated} />
        <Stat label="Ticks from cache" value={scaleSnapshot.ticksFromCache} />
        <Stat label="Last tick gen ms" value={scaleSnapshot.lastTickGenMs.toFixed(2)} />
        <Stat label="Max tick gen ms" value={scaleSnapshot.maxTickGenMs.toFixed(2)} />
        <Stat label="Tick cache hits" value={scaleSnapshot.cacheHits} />
        <Stat label="Tick cache misses" value={scaleSnapshot.cacheMisses} />
        <Stat label="Tick cache evictions" value={scaleSnapshot.cacheEvictions} />
        <Stat label="Last normalize ms" value={scaleSnapshot.lastNormalizationMs.toFixed(3)} />
        <Stat label="Max normalize ms" value={scaleSnapshot.maxNormalizationMs.toFixed(3)} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Zoom controller
        </span>
        <Stat label="Zoom ins" value={zoomSnapshot.zoomIns} />
        <Stat label="Zoom outs" value={zoomSnapshot.zoomOuts} />
        <Stat label="Zoom fits" value={zoomSnapshot.zoomFits} />
        <Stat label="Zoom by factor" value={zoomSnapshot.zoomByFactor} />
        <Stat label="Zoom level sets" value={zoomSnapshot.zoomSetLevels} />
        <Stat label="Wheel gestures" value={zoomSnapshot.wheelGestures} />
        <Stat label="Pinch gestures" value={zoomSnapshot.pinchGestures} />
        <Stat label="Preset activations" value={zoomSnapshot.presetActivations} />
        <Stat label="Shortcut invocations" value={zoomSnapshot.shortcutInvocations} />
        <Stat label="Min-constraint hits" value={zoomSnapshot.constraintHitsMin} />
        <Stat label="Max-constraint hits" value={zoomSnapshot.constraintHitsMax} />
        <Stat label="Noops suppressed" value={zoomSnapshot.noopsSuppressed} />
        <Stat label="Last zoom latency ms" value={zoomSnapshot.lastZoomLatencyMs.toFixed(3)} />
        <Stat label="Max zoom latency ms" value={zoomSnapshot.maxZoomLatencyMs.toFixed(3)} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Pan controller
        </span>
        <Stat label="Pans applied" value={panSnapshot.pansApplied} />
        <Stat label="Drags started" value={panSnapshot.dragsStarted} />
        <Stat label="Drags completed" value={panSnapshot.dragsCompleted} />
        <Stat label="Drags cancelled" value={panSnapshot.dragsCancelled} />
        <Stat label="Wheel gestures" value={panSnapshot.wheelGestures} />
        <Stat label="Keyboard steps" value={panSnapshot.keyboardSteps} />
        <Stat label="Center calls" value={panSnapshot.centerCalls} />
        <Stat label="Pan-to-time calls" value={panSnapshot.panToTimeCalls} />
        <Stat label="Total seconds panned" value={panSnapshot.totalAbsSecondsPanned.toFixed(3)} />
        <Stat label="Min-constraint hits" value={panSnapshot.constraintHitsMin} />
        <Stat label="Max-constraint hits" value={panSnapshot.constraintHitsMax} />
        <Stat label="Noops suppressed" value={panSnapshot.noopsSuppressed} />
        <Stat label="Longest drag ms" value={panSnapshot.dragLongestMs.toFixed(0)} />
        <Stat label="Last pan latency ms" value={panSnapshot.lastPanLatencyMs.toFixed(3)} />
        <Stat label="Max pan latency ms" value={panSnapshot.maxPanLatencyMs.toFixed(3)} />
      </dl>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
        <span className="col-span-2 text-[10px] uppercase tracking-widest text-subtle">
          Selection controller
        </span>
        <Stat label="Selection changes" value={selectionSnapshot.selectionChanges} />
        <Stat label="Pointer selects" value={selectionSnapshot.pointerSelects} />
        <Stat label="Keyboard selects" value={selectionSnapshot.keyboardSelects} />
        <Stat label="Programmatic" value={selectionSnapshot.programmaticSelects} />
        <Stat label="Clears" value={selectionSnapshot.clears} />
        <Stat label="Navigate next" value={selectionSnapshot.navigateNext} />
        <Stat label="Navigate prev" value={selectionSnapshot.navigatePrev} />
        <Stat label="Navigate home" value={selectionSnapshot.navigateHome} />
        <Stat label="Navigate end" value={selectionSnapshot.navigateEnd} />
        <Stat label="Center calls" value={selectionSnapshot.centerOnSelectionCalls} />
        <Stat label="Reveal calls" value={selectionSnapshot.revealCalls} />
        <Stat label="Restore calls" value={selectionSnapshot.restoreCalls} />
        <Stat label="Restore misses" value={selectionSnapshot.restoreMisses} />
        <Stat label="Noops suppressed" value={selectionSnapshot.noopsSuppressed} />
        <Stat
          label="Last change latency ms"
          value={selectionSnapshot.lastChangeLatencyMs.toFixed(3)}
        />
        <Stat
          label="Max change latency ms"
          value={selectionSnapshot.maxChangeLatencyMs.toFixed(3)}
        />
      </dl>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <>
      <dt className="text-[10px] uppercase tracking-widest text-subtle">{label}</dt>
      <dd className="tabular-nums text-text">{value}</dd>
    </>
  );
}
