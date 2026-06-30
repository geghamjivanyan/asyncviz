/**
 * Canonical timeline zoom controller.
 *
 * The controller is the single chokepoint for every interactive zoom
 * operation. It wraps the canonical :class:`TimelineScaleEngine` with
 * an imperative API + a small observable state machine:
 *
 *   * imperative methods (``zoomIn``, ``zoomOut``, ``zoomBy``,
 *     ``zoomToFit``, ``zoomToRange``, ``setZoomLevel``) translate
 *     user / toolbar input into scale-engine calls,
 *   * a :class:`TimelineZoomMetrics` instance records every call,
 *   * a small subscriber bus emits :type:`TimelineZoomState`
 *     snapshots so React components rerender on demand,
 *   * presets + cursor tracking land here so the toolbar + keyboard
 *     shortcuts don't reimplement them.
 *
 * The controller is framework-free TypeScript so it runs on a worker
 * thread later. React glue lives in :func:`useTimelineZoomController`.
 */

import type { TimelineScaleEngine } from "@/dashboard/timeline/scaling/TimelineScaleEngine";
import {
  resolveAnchorTime,
  cursorAnchor,
  centerAnchor,
} from "@/dashboard/timeline/zoom/TimelineZoomAnchoring";
import { wouldBreachConstraints } from "@/dashboard/timeline/zoom/TimelineZoomConstraints";
import { factorFromLevelDelta, levelToDuration } from "@/dashboard/timeline/zoom/utils/levelMath";
import { buildZoomState } from "@/dashboard/timeline/zoom/TimelineZoomState";
import {
  getTimelineZoomMetrics,
  type TimelineZoomMetrics,
} from "@/dashboard/timeline/zoom/TimelineZoomMetrics";
import {
  stepsToZoomFactor,
  wheelToZoomFactor,
  pinchToZoomFactor,
  type WheelGestureInput,
} from "@/dashboard/timeline/zoom/TimelineZoomGestures";
import {
  DEFAULT_ZOOM_CONFIG,
  type TimelineZoomState,
  type ZoomAnchor,
  type ZoomConfig,
  type ZoomPreset,
} from "@/dashboard/timeline/zoom/models/TimelineZoomModels";
import {
  traceZoomByFactor,
  traceZoomFit,
  traceZoomIn,
  traceZoomNoop,
  traceZoomOut,
  traceZoomPinch,
  traceZoomPreset,
  traceZoomSetLevel,
  traceZoomShortcut,
  traceZoomWheel,
} from "@/dashboard/timeline/zoom/TimelineZoomTracing";

export type ZoomStateListener = (state: TimelineZoomState) => void;

export interface TimelineZoomControllerOptions {
  engine: TimelineScaleEngine;
  metrics?: TimelineZoomMetrics;
  config?: Partial<ZoomConfig>;
}

export class TimelineZoomController {
  private readonly engine: TimelineScaleEngine;
  private readonly metrics: TimelineZoomMetrics;
  private readonly config: ZoomConfig;
  private readonly listeners = new Set<ZoomStateListener>();
  private cursorTimeSeconds: number | null = null;
  private state: TimelineZoomState;
  private engineUnsubscribe: (() => void) | null = null;
  private disposed = false;

  constructor(options: TimelineZoomControllerOptions) {
    this.engine = options.engine;
    this.metrics = options.metrics ?? getTimelineZoomMetrics();
    this.config = { ...DEFAULT_ZOOM_CONFIG, ...(options.config ?? {}) };
    this.state = buildZoomState(this.engine);
    this.engineUnsubscribe = this.engine.subscribe(() => {
      this.refreshState();
    });
  }

  // ── public surface ───────────────────────────────────────────────

  /** Current observable state — exposed for React rerender hooks. */
  currentState(): TimelineZoomState {
    return this.state;
  }

  /** Subscribe to zoom state changes. Returns an unsubscribe handle. */
  subscribe(listener: ZoomStateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Update the cursor world-time used by ``cursor``-anchored zoom. */
  setCursorTime(seconds: number | null): void {
    this.cursorTimeSeconds = seconds;
  }

  /** Convenience: zoom in one step. */
  zoomIn(anchor: ZoomAnchor = cursorAnchor()): void {
    if (this.disposed) return;
    const factor = stepsToZoomFactor(-1, this.config);
    this.metrics.recordZoomIn();
    traceZoomIn(`factor=${factor}`);
    this.zoomBy(factor, anchor);
  }

  /** Convenience: zoom out one step. */
  zoomOut(anchor: ZoomAnchor = cursorAnchor()): void {
    if (this.disposed) return;
    const factor = stepsToZoomFactor(1, this.config);
    this.metrics.recordZoomOut();
    traceZoomOut(`factor=${factor}`);
    this.zoomBy(factor, anchor);
  }

  /** Apply a multiplicative zoom factor around the anchor. */
  zoomBy(factor: number, anchor: ZoomAnchor = centerAnchor()): void {
    if (this.disposed) return;
    if (!Number.isFinite(factor) || factor <= 0 || factor === 1) {
      this.metrics.recordNoopSuppressed();
      traceZoomNoop(`factor=${factor}`);
      return;
    }
    const scale = this.engine.currentScale();
    const constraints = this.engine.currentConstraints();
    const breach = wouldBreachConstraints(scale.durationSeconds, factor, constraints);
    if (breach !== null && this.state.atMin && factor < 1) {
      this.metrics.recordConstraintHit("min");
      this.metrics.recordNoopSuppressed();
      traceZoomNoop("at-min");
      return;
    }
    if (breach !== null && this.state.atMax && factor > 1) {
      this.metrics.recordConstraintHit("max");
      this.metrics.recordNoopSuppressed();
      traceZoomNoop("at-max");
      return;
    }
    const anchorTime = resolveAnchorTime(anchor, {
      scale,
      cursorTimeSeconds: this.cursorTimeSeconds,
    });
    const start = nowMs();
    this.engine.zoomAroundTime(anchorTime, factor);
    this.metrics.recordZoomByFactor();
    this.metrics.recordZoomLatency(nowMs() - start);
    traceZoomByFactor(`anchor=${anchorTime} factor=${factor}`);
  }

  /** Fit the scale window to ``[start, end]``. */
  zoomToRange(startSeconds: number, endSeconds: number, kind: string = "manual"): void {
    if (this.disposed) return;
    if (!(endSeconds > startSeconds)) {
      this.metrics.recordNoopSuppressed();
      traceZoomNoop("invalid-range");
      return;
    }
    const start = nowMs();
    this.engine.fitToRange(startSeconds, endSeconds);
    this.metrics.recordZoomFit(kind);
    this.metrics.recordZoomLatency(nowMs() - start);
    traceZoomFit(`range=${startSeconds}..${endSeconds} kind=${kind}`);
  }

  /** Activate a preset — equivalent to ``zoomToRange`` with the
   *  preset's bounds + a labeled fit metric. */
  activatePreset(preset: ZoomPreset): void {
    if (this.disposed) return;
    this.metrics.recordPresetActivation();
    traceZoomPreset(`kind=${preset.kind}`);
    this.zoomToRange(preset.startSeconds, preset.endSeconds, preset.kind);
  }

  /** Set the normalized zoom level in ``[0, 1]`` around the active
   *  cursor (falls back to center). */
  setZoomLevel(level: number, anchor: ZoomAnchor = cursorAnchor()): void {
    if (this.disposed) return;
    const constraints = this.engine.currentConstraints();
    const targetDuration = levelToDuration(level, {
      minDurationSeconds: constraints.minDurationSeconds,
      maxDurationSeconds: constraints.maxDurationSeconds,
    });
    const scale = this.engine.currentScale();
    const factor = scale.durationSeconds === 0 ? 1 : targetDuration / scale.durationSeconds;
    this.metrics.recordZoomSetLevel();
    traceZoomSetLevel(`level=${level} factor=${factor}`);
    this.zoomBy(factor, anchor);
  }

  /** Apply a level delta — used by keyboard shortcuts (one step
   *  per Ctrl+= / Ctrl+−). */
  applyLevelDelta(levelDelta: number, anchor: ZoomAnchor = cursorAnchor()): void {
    if (this.disposed) return;
    const constraints = this.engine.currentConstraints();
    const factor = factorFromLevelDelta(this.engine.currentScale().durationSeconds, levelDelta, {
      minDurationSeconds: constraints.minDurationSeconds,
      maxDurationSeconds: constraints.maxDurationSeconds,
    });
    this.zoomBy(factor, anchor);
  }

  /** Apply a wheel gesture — typically from a wheel/trackpad event. */
  applyWheelGesture(input: WheelGestureInput, anchor: ZoomAnchor = cursorAnchor()): void {
    if (this.disposed) return;
    this.metrics.recordWheel();
    traceZoomWheel(`deltaY=${input.deltaY} mode=${input.deltaMode}`);
    const factor = wheelToZoomFactor(input, this.config);
    this.zoomBy(factor, anchor);
  }

  /** Apply a pinch gesture — typically from a touch event. */
  applyPinchGesture(ratio: number, anchor: ZoomAnchor = cursorAnchor()): void {
    if (this.disposed) return;
    this.metrics.recordPinch();
    traceZoomPinch(`ratio=${ratio}`);
    const factor = pinchToZoomFactor(ratio);
    this.zoomBy(factor, anchor);
  }

  /** Record that a keyboard shortcut fired. The actual zoom call is
   *  the consumer's responsibility — this helper exists so metrics
   *  aren't double-counted when ``zoomIn`` / ``zoomOut`` call into
   *  ``zoomBy``. */
  recordShortcut(detail: string): void {
    this.metrics.recordShortcut();
    traceZoomShortcut(detail);
  }

  /** Snapshot exposed for diagnostics. */
  metricsSnapshot() {
    return this.metrics.snapshot();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.engineUnsubscribe?.();
    this.engineUnsubscribe = null;
    this.listeners.clear();
  }

  // ── internals ────────────────────────────────────────────────────

  private refreshState(): void {
    this.state = buildZoomState(this.engine);
    for (const listener of this.listeners) {
      try {
        listener(this.state);
      } catch (err) {
        console.error("TimelineZoomController: listener threw", err);
      }
    }
  }
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
