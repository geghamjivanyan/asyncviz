/**
 * Immutable time-axis scale primitive.
 *
 * A scale captures one ``(timeStart, timeEnd, widthPx)`` tuple and
 * pre-computes ``pixelsPerSecond`` + ``secondsPerPixel``. The class is
 * intentionally allocation-light + read-only so the engine can swap
 * scales without copying state; consumers only ever hold a reference.
 *
 * Transforms are pure — replay frames built with identical scales
 * produce byte-identical coordinates.
 */

import {
  SCALE_EPSILON_SECONDS,
  isNumericallyUnsafe,
} from "@/dashboard/timeline/scaling/utils/numerics";
import type { TimelineScaleSnapshot } from "@/dashboard/timeline/scaling/models/TimelineScaleModels";

export class TimelineTimeScale implements TimelineScaleSnapshot {
  readonly timeStart: number;
  readonly timeEnd: number;
  readonly widthPx: number;
  readonly durationSeconds: number;
  readonly pixelsPerSecond: number;
  readonly secondsPerPixel: number;
  readonly key: string;

  constructor(timeStart: number, timeEnd: number, widthPx: number) {
    if (!Number.isFinite(timeStart) || !Number.isFinite(timeEnd)) {
      throw new RangeError("TimelineTimeScale: non-finite time bounds");
    }
    if (!Number.isFinite(widthPx) || widthPx <= 0) {
      throw new RangeError("TimelineTimeScale: non-positive widthPx");
    }
    this.timeStart = timeStart;
    this.timeEnd = timeEnd;
    this.widthPx = widthPx;
    const duration = Math.max(SCALE_EPSILON_SECONDS, timeEnd - timeStart);
    this.durationSeconds = duration;
    this.pixelsPerSecond = widthPx / duration;
    this.secondsPerPixel = duration / widthPx;
    this.key = `${timeStart}|${timeEnd}|${widthPx}`;
  }

  /** Pure: map world seconds → CSS pixel x. */
  timeToX(seconds: number): number {
    return (seconds - this.timeStart) * this.pixelsPerSecond;
  }

  /** Pure: map CSS pixel x → world seconds. */
  xToTime(x: number): number {
    return this.timeStart + x * this.secondsPerPixel;
  }

  /** Pure: ``true`` when ``[s, e]`` overlaps the scale's window. */
  intersectsTime(startSeconds: number, endSeconds: number): boolean {
    return endSeconds >= this.timeStart && startSeconds <= this.timeEnd;
  }

  /** Pure: project an inclusive time range to a clipped CSS span.
   *  Returns ``null`` when the span is fully outside the window. */
  projectRange(
    startSeconds: number,
    endSeconds: number,
  ): { x0: number; x1: number; clippedLeft: boolean; clippedRight: boolean } | null {
    if (!this.intersectsTime(startSeconds, endSeconds)) return null;
    const rawX0 = this.timeToX(startSeconds);
    const rawX1 = this.timeToX(endSeconds);
    let x0 = rawX0;
    let x1 = rawX1;
    let clippedLeft = false;
    let clippedRight = false;
    if (x0 < 0) {
      x0 = 0;
      clippedLeft = true;
    }
    if (x1 > this.widthPx) {
      x1 = this.widthPx;
      clippedRight = true;
    }
    return { x0, x1, clippedLeft, clippedRight };
  }

  /** ``true`` when the scale parameters fit inside the engine's
   *  numerical safety bounds. */
  isNumericallySafe(): boolean {
    return (
      !isNumericallyUnsafe(this.timeStart) &&
      !isNumericallyUnsafe(this.timeEnd) &&
      !isNumericallyUnsafe(this.pixelsPerSecond) &&
      Number.isFinite(this.secondsPerPixel)
    );
  }
}

/** Convenience: build a scale, swallowing degenerate inputs by
 *  falling back to a defensive minimum width. Useful for the React
 *  hooks that may briefly receive zero-width viewports. */
export function safeScale(timeStart: number, timeEnd: number, widthPx: number): TimelineTimeScale {
  const width = widthPx > 0 ? widthPx : 1;
  const end = timeEnd > timeStart ? timeEnd : timeStart + SCALE_EPSILON_SECONDS;
  return new TimelineTimeScale(timeStart, end, width);
}
