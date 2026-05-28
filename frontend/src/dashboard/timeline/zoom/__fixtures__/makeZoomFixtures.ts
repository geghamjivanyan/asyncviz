/**
 * Tiny shared builders for the zoom test suite.
 */

import { TimelineScaleEngine } from "@/dashboard/timeline/scaling/TimelineScaleEngine";

export interface MakeEngineOptions {
  timeStart?: number;
  timeEnd?: number;
  widthPx?: number;
  minDurationSeconds?: number;
  maxDurationSeconds?: number;
}

export function buildEngine(options: MakeEngineOptions = {}): TimelineScaleEngine {
  return new TimelineScaleEngine({
    initialTimeStart: options.timeStart ?? 0,
    initialTimeEnd: options.timeEnd ?? 10,
    initialViewport: { widthPx: options.widthPx ?? 800, devicePixelRatio: 1 },
    constraints: {
      minDurationSeconds: options.minDurationSeconds ?? 0.001,
      maxDurationSeconds: options.maxDurationSeconds ?? 1000,
    },
  });
}
