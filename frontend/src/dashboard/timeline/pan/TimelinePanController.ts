/**
 * Canonical timeline pan controller.
 *
 * The controller is the single chokepoint for every interactive
 * panning operation. It wraps the canonical
 * :class:`TimelineScaleEngine` with an imperative API + a small
 * observable state machine:
 *
 *   * imperative methods (``panLeft``, ``panRight``, ``panBy``,
 *     ``panBySeconds``, ``panToTime``, ``centerOnTime``,
 *     ``beginDrag``/``updateDrag``/``endDrag``,
 *     ``applyWheelGesture``, ``applyKeyboardStep``) translate user /
 *     toolbar input into scale-engine calls,
 *   * a :class:`TimelinePanMetrics` instance records every call,
 *   * a small subscriber bus emits :type:`TimelinePanState`
 *     snapshots so React components rerender on demand,
 *   * a :class:`TimelinePanMomentum` instance records velocity
 *     samples so the future inertial controller has a stable buffer
 *     to consume from day one.
 *
 * The controller is framework-free TypeScript so it runs on a worker
 * thread later. React glue lives in :func:`useTimelinePanController`.
 */

import type { TimelineScaleEngine } from "@/dashboard/timeline/scaling/TimelineScaleEngine";
import {
  makeDragAnchor,
  timeStartFromAnchor,
} from "@/dashboard/timeline/pan/TimelinePanAnchoring";
import {
  dragDeltaToSeconds,
  stepsToPanSeconds,
  wheelToPanSeconds,
} from "@/dashboard/timeline/pan/TimelinePanGestures";
import {
  clampPanTimeStart,
  mergeBounds,
  panWouldExceedBound,
  viewportEdgeState,
} from "@/dashboard/timeline/pan/TimelinePanConstraints";
import {
  TimelinePanMomentum,
} from "@/dashboard/timeline/pan/TimelinePanMomentum";
import {
  deltaToCenter,
  deltaToTimeStart,
} from "@/dashboard/timeline/pan/utils/panMath";
import {
  getTimelinePanMetrics,
  type TimelinePanMetrics,
} from "@/dashboard/timeline/pan/TimelinePanMetrics";
import {
  DEFAULT_PAN_CONFIG,
  type PanBounds,
  type PanConfig,
  type PanDragAnchor,
  type PanReason,
  type TimelinePanState,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";
import {
  tracePan,
  tracePanCenter,
  tracePanConstraintHit,
  tracePanDragCancel,
  tracePanDragEnd,
  tracePanDragStart,
  tracePanDragUpdate,
  tracePanKeyboard,
  tracePanNoop,
  tracePanToTime,
  tracePanWheel,
} from "@/dashboard/timeline/pan/TimelinePanTracing";

export type PanStateListener = (state: TimelinePanState) => void;

export interface TimelinePanControllerOptions {
  engine: TimelineScaleEngine;
  metrics?: TimelinePanMetrics;
  config?: Partial<PanConfig>;
  bounds?: Partial<PanBounds>;
  momentum?: TimelinePanMomentum;
}

export class TimelinePanController {
  private readonly engine: TimelineScaleEngine;
  private readonly metrics: TimelinePanMetrics;
  private readonly config: PanConfig;
  private readonly listeners = new Set<PanStateListener>();
  private readonly momentum: TimelinePanMomentum;
  private bounds: PanBounds;
  private state: TimelinePanState;
  private dragAnchor: PanDragAnchor | null = null;
  private dragLastTimeStart = 0;
  private dragLastSampleMs = 0;
  private engineUnsubscribe: (() => void) | null = null;
  private disposed = false;

  constructor(options: TimelinePanControllerOptions) {
    this.engine = options.engine;
    this.metrics = options.metrics ?? getTimelinePanMetrics();
    this.config = { ...DEFAULT_PAN_CONFIG, ...(options.config ?? {}) };
    this.bounds = mergeBounds(options.bounds);
    this.momentum = options.momentum ?? new TimelinePanMomentum();
    this.state = this.buildState();
    this.engineUnsubscribe = this.engine.subscribe(() => {
      this.refreshState();
    });
  }

  // ── public surface ───────────────────────────────────────────────

  currentState(): TimelinePanState {
    return this.state;
  }

  currentBounds(): PanBounds {
    return this.bounds;
  }

  /** Replace pan bounds at runtime — used when the data range
   *  changes (e.g. when a new replay loads). */
  setBounds(bounds: Partial<PanBounds> | null): void {
    this.bounds = mergeBounds(bounds ?? undefined);
    this.refreshState();
  }

  subscribe(listener: PanStateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Pan left one step (default: ``keyboardStepFraction`` of the
   *  visible window). */
  panLeft(args: { shift?: boolean; reason?: PanReason } = {}): void {
    if (this.disposed) return;
    const delta = stepsToPanSeconds(-1, this.engine.currentScale().durationSeconds, {
      shift: args.shift,
      config: this.config,
    });
    this.metrics.recordKeyboard();
    tracePanKeyboard(`step=-1 shift=${Boolean(args.shift)} delta=${delta}`);
    this.panBySeconds(delta, args.reason ?? "keyboard");
  }

  /** Pan right one step. */
  panRight(args: { shift?: boolean; reason?: PanReason } = {}): void {
    if (this.disposed) return;
    const delta = stepsToPanSeconds(1, this.engine.currentScale().durationSeconds, {
      shift: args.shift,
      config: this.config,
    });
    this.metrics.recordKeyboard();
    tracePanKeyboard(`step=+1 shift=${Boolean(args.shift)} delta=${delta}`);
    this.panBySeconds(delta, args.reason ?? "keyboard");
  }

  /** Pan by an explicit pixel delta — used by drag + wheel paths. */
  panByPixels(deltaXPx: number, reason: PanReason = "manual"): void {
    if (this.disposed) return;
    const seconds = dragDeltaToSeconds(deltaXPx, this.engine.currentScale().secondsPerPixel);
    this.panBySeconds(seconds, reason);
  }

  /** Pan by an explicit time delta — the canonical mutation. */
  panBySeconds(deltaSeconds: number, reason: PanReason = "manual"): void {
    if (this.disposed) return;
    if (!Number.isFinite(deltaSeconds) || deltaSeconds === 0) {
      this.metrics.recordNoopSuppressed();
      tracePanNoop(`reason=${reason} delta=${deltaSeconds}`);
      return;
    }
    const scale = this.engine.currentScale();
    const breach = panWouldExceedBound(deltaSeconds, {
      timeStartSeconds: scale.timeStart,
      durationSeconds: scale.durationSeconds,
      bounds: this.bounds,
    });
    if (breach === "min" && this.state.atMinTime) {
      this.metrics.recordConstraintHit("min");
      this.metrics.recordNoopSuppressed();
      tracePanConstraintHit("at-min");
      return;
    }
    if (breach === "max" && this.state.atMaxTime) {
      this.metrics.recordConstraintHit("max");
      this.metrics.recordNoopSuppressed();
      tracePanConstraintHit("at-max");
      return;
    }
    const candidate = scale.timeStart + deltaSeconds;
    const clampedStart = clampPanTimeStart(candidate, {
      timeStartSeconds: scale.timeStart,
      durationSeconds: scale.durationSeconds,
      bounds: this.bounds,
    });
    if (clampedStart === scale.timeStart) {
      this.metrics.recordNoopSuppressed();
      tracePanNoop("clamped-to-current");
      return;
    }
    const actualDelta = clampedStart - scale.timeStart;
    const start = nowMs();
    this.engine.setTimeWindow(clampedStart, clampedStart + scale.durationSeconds);
    this.metrics.recordPan(reason, actualDelta);
    this.metrics.recordPanLatency(nowMs() - start);
    tracePan(`reason=${reason} delta=${actualDelta}`);
  }

  /** Move the viewport so its left edge sits at ``timeSeconds``. */
  panToTime(timeSeconds: number): void {
    if (this.disposed) return;
    const scale = this.engine.currentScale();
    const delta = deltaToTimeStart(timeSeconds, scale.timeStart);
    this.metrics.recordPanToTime();
    tracePanToTime(`target=${timeSeconds} delta=${delta}`);
    this.panBySeconds(delta, "to-time");
  }

  /** Center the viewport on ``timeSeconds``. */
  centerOnTime(timeSeconds: number): void {
    if (this.disposed) return;
    const scale = this.engine.currentScale();
    const delta = deltaToCenter(timeSeconds, scale.timeStart, scale.durationSeconds);
    this.metrics.recordCenter();
    tracePanCenter(`target=${timeSeconds} delta=${delta}`);
    this.panBySeconds(delta, "center");
  }

  // ── drag lifecycle ───────────────────────────────────────────────

  /** Begin a pointer drag. */
  beginDrag(args: { pointerXCss: number; pointerTimeSeconds: number }): void {
    if (this.disposed) return;
    const scale = this.engine.currentScale();
    this.dragAnchor = makeDragAnchor({
      pointerXCss: args.pointerXCss,
      pointerTimeSeconds: args.pointerTimeSeconds,
      timeStartSeconds: scale.timeStart,
      timeEndSeconds: scale.timeEnd,
    });
    this.dragLastTimeStart = scale.timeStart;
    this.dragLastSampleMs = nowMs();
    this.momentum.reset();
    this.metrics.recordDragStart();
    this.refreshState();
    tracePanDragStart(`x=${args.pointerXCss} t=${args.pointerTimeSeconds}`);
  }

  /** Update an in-flight drag with the current pointer position. */
  updateDrag(args: { pointerXCss: number }): void {
    if (this.disposed) return;
    if (this.dragAnchor === null) return;
    const scale = this.engine.currentScale();
    const candidate = timeStartFromAnchor(
      this.dragAnchor,
      args.pointerXCss,
      scale.secondsPerPixel,
    );
    const clampedStart = clampPanTimeStart(candidate, {
      timeStartSeconds: scale.timeStart,
      durationSeconds: scale.durationSeconds,
      bounds: this.bounds,
    });
    if (clampedStart === scale.timeStart) {
      tracePanDragUpdate(`x=${args.pointerXCss} noop`);
      return;
    }
    const actualDelta = clampedStart - scale.timeStart;
    const start = nowMs();
    this.engine.setTimeWindow(clampedStart, clampedStart + scale.durationSeconds);
    this.metrics.recordPan("drag", actualDelta);
    this.metrics.recordPanLatency(nowMs() - start);
    // Velocity sample for the future inertial controller.
    const now = nowMs();
    const sampleDeltaMs = now - this.dragLastSampleMs;
    const sampleDeltaSeconds = clampedStart - this.dragLastTimeStart;
    if (sampleDeltaMs > 0) {
      this.momentum.push({
        deltaSeconds: sampleDeltaSeconds,
        deltaMs: sampleDeltaMs,
        atMs: now,
      });
    }
    this.dragLastTimeStart = clampedStart;
    this.dragLastSampleMs = now;
    tracePanDragUpdate(`x=${args.pointerXCss} delta=${actualDelta}`);
  }

  /** Finalize a drag — emits a single ``dragComplete`` metric and
   *  clears the anchor. */
  endDrag(): void {
    if (this.disposed) return;
    if (this.dragAnchor === null) return;
    const anchor = this.dragAnchor;
    this.dragAnchor = null;
    const now = nowMs();
    const durationMs = now - anchor.startedAtMs;
    const secondsMoved = this.engine.currentScale().timeStart - anchor.initialTimeStartSeconds;
    this.metrics.recordDragComplete({ durationMs, secondsMoved });
    this.refreshState();
    tracePanDragEnd(`durationMs=${durationMs} secondsMoved=${secondsMoved}`);
  }

  /** Cancel an in-flight drag without committing. */
  cancelDrag(): void {
    if (this.disposed) return;
    if (this.dragAnchor === null) return;
    this.dragAnchor = null;
    this.momentum.reset();
    this.metrics.recordDragCancel();
    this.refreshState();
    tracePanDragCancel("cancelled");
  }

  /** ``true`` while a drag is in flight. */
  isDragging(): boolean {
    return this.dragAnchor !== null;
  }

  /** Apply a horizontal wheel gesture (e.g. trackpad two-finger). */
  applyWheelGesture(args: { deltaXPx: number }): void {
    if (this.disposed) return;
    const seconds = wheelToPanSeconds(
      args.deltaXPx,
      this.engine.currentScale().secondsPerPixel,
      this.config,
    );
    this.metrics.recordWheel();
    tracePanWheel(`deltaX=${args.deltaXPx} delta=${seconds}`);
    this.panBySeconds(seconds, "wheel");
  }

  /** Apply a keyboard step (1 = right, -1 = left). */
  applyKeyboardStep(steps: number, shift = false): void {
    if (this.disposed) return;
    if (!Number.isFinite(steps) || steps === 0) return;
    if (steps < 0) this.panLeft({ shift });
    else this.panRight({ shift });
  }

  /** Snapshot exposed for diagnostics. */
  metricsSnapshot() {
    return this.metrics.snapshot();
  }

  /** Read the momentum samples — used by the future inertial loop. */
  momentumVelocity(): number {
    return this.momentum.velocity(nowMs());
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.engineUnsubscribe?.();
    this.engineUnsubscribe = null;
    this.dragAnchor = null;
    this.listeners.clear();
  }

  // ── internals ────────────────────────────────────────────────────

  private buildState(): TimelinePanState {
    const scale = this.engine.currentScale();
    const edges = viewportEdgeState({
      timeStartSeconds: scale.timeStart,
      durationSeconds: scale.durationSeconds,
      bounds: this.bounds,
    });
    return {
      timeStartSeconds: scale.timeStart,
      timeEndSeconds: scale.timeEnd,
      durationSeconds: scale.durationSeconds,
      pixelsPerSecond: scale.pixelsPerSecond,
      dragging: this.dragAnchor !== null,
      atMinTime: edges.atMin,
      atMaxTime: edges.atMax,
      minTimeSeconds: this.bounds.minTimeSeconds,
      maxTimeSeconds: this.bounds.maxTimeSeconds,
      scaleKey: scale.key,
    };
  }

  private refreshState(): void {
    this.state = this.buildState();
    for (const listener of this.listeners) {
      try {
        listener(this.state);
      } catch (err) {
        console.error("TimelinePanController: listener threw", err);
      }
    }
  }
}

function nowMs(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
