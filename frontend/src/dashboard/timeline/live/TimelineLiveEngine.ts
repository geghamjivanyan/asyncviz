/**
 * Canonical live timeline update engine.
 *
 * The engine sits between the runtime websocket / store and the
 * canvas :class:`TimelineRenderer`. It is the *only* component that
 * decides when the canvas should redraw — every other path
 * (websocket envelope, replay batch, animation tick, manual
 * invalidation) flows through here.
 *
 * Composition:
 *
 *   * :class:`TimelineInvalidationTracker` — accumulates dirty
 *     regions inside one batching window,
 *   * :class:`TimelineUpdateBatcher` — microtask / rAF window that
 *     coalesces accumulations into one flush,
 *   * :class:`TimelineDeltaProcessor` — translates envelopes into
 *     narrow invalidations,
 *   * :class:`TimelineReplayCoordinator` — manages replay-batch +
 *     replay → live transition,
 *   * :class:`TimelineAnimationClock` — drives continuous rAF while
 *     active segments are in flight,
 *   * :class:`TimelineFrameScheduler` — pushes flushes to the
 *     renderer with optional throttling,
 *   * :class:`TimelineLiveMetrics` — observability.
 *
 * The engine is framework-free TypeScript so it runs on a worker
 * thread later. React glue lives in :func:`useTimelineLiveEngine`.
 */

import type { RuntimeEnvelope } from "@/types/runtime";
import type { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";
import { TimelineUpdateBatcher, type BatchingOptions } from "@/dashboard/timeline/live/TimelineUpdateBatching";
import { TimelineDeltaProcessor } from "@/dashboard/timeline/live/TimelineDeltaProcessor";
import { TimelineReplayCoordinator } from "@/dashboard/timeline/live/TimelineReplayCoordinator";
import { TimelineAnimationClock, type AnimationClockOptions } from "@/dashboard/timeline/live/TimelineAnimationClock";
import {
  TimelineFrameScheduler,
  type FrameSchedulerOptions,
} from "@/dashboard/timeline/live/TimelineFrameScheduler";
import {
  getTimelineLiveMetrics,
  type TimelineLiveMetrics,
} from "@/dashboard/timeline/live/TimelineLiveMetrics";
import {
  batchToRendererReason,
  batchIsActionable,
  batchIsActiveTickOnly,
} from "@/dashboard/timeline/live/TimelineDirtyRegions";
import type {
  InvalidationBatch,
  TimelineLiveMode,
} from "@/dashboard/timeline/live/models/TimelineLiveModels";
import {
  traceActiveTick,
  traceEnvelope,
  traceFlush,
  traceFrameRequest,
  traceInvalidate,
  traceModeChange,
  traceReplay,
} from "@/dashboard/timeline/live/TimelineUpdateTracing";

export interface TimelineLiveEngineOptions {
  renderer: TimelineRenderer;
  batching?: BatchingOptions;
  animation?: AnimationClockOptions;
  frameScheduler?: FrameSchedulerOptions;
  metrics?: TimelineLiveMetrics;
  /** Auto-start in ``live`` mode when ``true`` (default). */
  startLive?: boolean;
}

export class TimelineLiveEngine {
  private readonly renderer: TimelineRenderer;
  private readonly tracker: TimelineInvalidationTracker;
  private readonly batcher: TimelineUpdateBatcher;
  private readonly processor: TimelineDeltaProcessor;
  private readonly replayCoordinator: TimelineReplayCoordinator;
  private readonly animationClock: TimelineAnimationClock;
  private readonly frameScheduler: TimelineFrameScheduler;
  private readonly metrics: TimelineLiveMetrics;
  private disposed = false;
  private lastFlushScheduleMs = 0;

  constructor(options: TimelineLiveEngineOptions) {
    this.renderer = options.renderer;
    this.metrics = options.metrics ?? getTimelineLiveMetrics();
    this.tracker = new TimelineInvalidationTracker();
    this.processor = new TimelineDeltaProcessor();
    this.replayCoordinator = new TimelineReplayCoordinator({
      processor: this.processor,
      tracker: this.tracker,
    });
    this.frameScheduler = new TimelineFrameScheduler(
      { invalidate: (reason) => this.renderer.invalidate(reason) },
      options.frameScheduler,
    );
    this.animationClock = new TimelineAnimationClock(
      () => this.onAnimationTick(),
      options.animation,
    );
    this.batcher = new TimelineUpdateBatcher(() => this.flushBatchInternal(), options.batching);
    if (options.startLive ?? true) this.goLive();
    else this.metrics.setMode(this.replayCoordinator.currentMode());
  }

  // ── public API ───────────────────────────────────────────────────

  /** Apply a single envelope to the engine. The store should already
   *  have ingested it — this only drives the canvas redraw path. */
  processEnvelope(envelope: RuntimeEnvelope): void {
    if (this.disposed) return;
    const result = this.processor.process(envelope, this.tracker);
    this.metrics.recordEnvelope(result.suppressed);
    traceEnvelope(`type=${envelope.type} suppressed=${result.suppressed} regions=${result.regionsPushed}`);
    if (this.replayCoordinator.currentMode() !== "replay") {
      this.metrics.recordLiveEnvelope();
    }
    if (result.invalidated) {
      this.scheduleFlush();
    }
  }

  /** Apply a replay batch. The coordinator flushes a single ``replay``
   *  invalidation on top of the per-envelope deltas. */
  processReplayBatch(envelopes: readonly RuntimeEnvelope[]): void {
    if (this.disposed) return;
    this.replayCoordinator.beginReplay();
    this.metrics.setMode("replay");
    traceReplay(`begin envelopes=${envelopes.length}`);
    const result = this.replayCoordinator.applyReplayBatch(envelopes);
    this.metrics.recordReplayBatch(result.applied);
    traceReplay(`applied=${result.applied} suppressed=${result.suppressed}`);
    this.batcher.flushNow();
  }

  /** Transition out of replay mode back to live streaming. */
  goLive(): void {
    this.replayCoordinator.goLive();
    this.metrics.setMode("live");
    traceModeChange("live");
  }

  /** Pause both deltas and the animation clock. */
  pause(): void {
    this.replayCoordinator.pause();
    this.animationClock.pause();
    this.metrics.setMode("paused");
    traceModeChange("paused");
  }

  /** Resume after a pause. */
  resume(): void {
    if (this.replayCoordinator.currentMode() === "paused") {
      this.replayCoordinator.goLive();
      this.metrics.setMode("live");
      traceModeChange("live");
    }
    this.animationClock.resume();
  }

  /** Manual full-viewport invalidation — used after a hydration. */
  invalidateAll(): void {
    if (this.disposed) return;
    this.tracker.push({ reason: "viewport" });
    traceInvalidate("viewport (manual)");
    this.scheduleFlush();
  }

  /** Manual row invalidation — public hook for selection state. */
  invalidateRow(taskId: string, sequence: number | null = null): void {
    if (this.disposed) return;
    this.tracker.push({ reason: "row", taskIds: [taskId], sequence });
    traceInvalidate(`row task=${taskId}`);
    this.scheduleFlush();
  }

  /** Manual segment invalidation. */
  invalidateSegment(segmentId: string, taskId?: string, sequence: number | null = null): void {
    if (this.disposed) return;
    this.tracker.push({
      reason: "segment",
      segmentIds: [segmentId],
      taskIds: taskId !== undefined ? [taskId] : undefined,
      sequence,
    });
    traceInvalidate(`segment id=${segmentId} task=${taskId ?? "?"}`);
    this.scheduleFlush();
  }

  /** Drive the active-segment count for the animation clock. */
  setActiveSegmentCount(count: number): void {
    if (this.disposed) return;
    this.animationClock.setActiveSegmentCount(count);
  }

  /** Schedule a flush (idempotent inside the batch window). */
  scheduleFlush(): void {
    if (this.disposed) return;
    if (!this.tracker.isDirty()) {
      this.metrics.recordFlushSkippedIdle();
      return;
    }
    this.lastFlushScheduleMs =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    this.metrics.recordFlushScheduled();
    this.batcher.schedule();
  }

  /** Force-flush queued invalidations into the renderer right now. */
  flushNow(): void {
    if (this.disposed) return;
    this.batcher.flushNow();
  }

  /** Public access to the current mode. */
  mode(): TimelineLiveMode {
    return this.replayCoordinator.currentMode();
  }

  rendererTarget(): TimelineRenderer {
    return this.renderer;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.batcher.dispose();
    this.animationClock.dispose();
    this.tracker.clear();
  }

  metricsSnapshot() {
    return this.metrics.snapshot();
  }

  // ── internals ────────────────────────────────────────────────────

  private flushBatchInternal(): void {
    if (this.disposed) return;
    if (!this.tracker.isDirty()) {
      this.metrics.recordFlushSkippedIdle();
      return;
    }
    const batch: InvalidationBatch = this.tracker.drain();
    if (!batchIsActionable(batch)) {
      this.metrics.recordFlushSkippedIdle();
      return;
    }
    this.metrics.recordFlushExecuted();
    const now = typeof performance !== "undefined" ? performance.now() : Date.now();
    const latency = Math.max(0, now - this.lastFlushScheduleMs);
    this.metrics.recordBatch(batch.regionCount, latency, now);
    for (const reason of batch.reasons) this.metrics.recordInvalidation(reason);
    traceFlush(
      `regions=${batch.regionCount} reasons=${batch.reasons.join(",")} latency=${latency.toFixed(2)}ms`,
    );
    const rendererReason = batchToRendererReason(batch);
    if (batchIsActiveTickOnly(batch)) {
      traceFrameRequest("active-tick");
    } else {
      traceFrameRequest(rendererReason);
    }
    this.frameScheduler.requestFrame(rendererReason);
  }

  private onAnimationTick(): void {
    if (this.disposed) return;
    this.tracker.push({ reason: "active-tick" });
    this.metrics.recordActiveTick(false);
    traceActiveTick("tick");
    this.scheduleFlush();
  }
}
