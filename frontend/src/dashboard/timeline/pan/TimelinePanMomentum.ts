/**
 * Pure momentum primitive — the scaffolding the future inertial pan
 * controller drives. The math + data shape land today so the
 * inertial controller plugs in without changing any API.
 *
 * The current controller doesn't drive inertia — but it does record
 * velocity samples during a drag so the inertial controller has a
 * stable buffer to consume the moment it ships.
 */

import type {
  PanVelocitySample,
} from "@/dashboard/timeline/pan/models/TimelinePanModels";

const DEFAULT_WINDOW_MS = 120;
const DEFAULT_CAPACITY = 16;

export interface MomentumOptions {
  /** Sliding window in ms used to compute the smoothed velocity. */
  windowMs?: number;
  /** Maximum number of stored samples. */
  capacity?: number;
}

export class TimelinePanMomentum {
  private samples: PanVelocitySample[] = [];
  private readonly windowMs: number;
  private readonly capacity: number;

  constructor(options: MomentumOptions = {}) {
    this.windowMs = Math.max(10, options.windowMs ?? DEFAULT_WINDOW_MS);
    this.capacity = Math.max(2, options.capacity ?? DEFAULT_CAPACITY);
  }

  /** Push a new sample. */
  push(sample: PanVelocitySample): void {
    this.samples.push(sample);
    while (this.samples.length > this.capacity) this.samples.shift();
  }

  /** Smoothed velocity (seconds per ms) across the active window. */
  velocity(nowMs: number): number {
    if (this.samples.length === 0) return 0;
    const cutoff = nowMs - this.windowMs;
    let totalDelta = 0;
    let totalMs = 0;
    for (const sample of this.samples) {
      if (sample.atMs < cutoff) continue;
      totalDelta += sample.deltaSeconds;
      totalMs += sample.deltaMs;
    }
    if (totalMs <= 0) return 0;
    return totalDelta / totalMs;
  }

  /** Drop all stored samples — call on drag-start. */
  reset(): void {
    this.samples = [];
  }

  size(): number {
    return this.samples.length;
  }
}

/** Pure: apply exponential decay to a velocity, simulating one step
 *  of the future inertial loop. ``decay ∈ (0, 1]`` — larger values
 *  decay faster. */
export function decayVelocity(
  velocitySecondsPerMs: number,
  elapsedMs: number,
  decayPerMs: number,
): number {
  if (!Number.isFinite(velocitySecondsPerMs)) return 0;
  const damping = Math.max(0, Math.min(1, decayPerMs));
  if (damping === 0 || elapsedMs <= 0) return velocitySecondsPerMs;
  return velocitySecondsPerMs * Math.pow(1 - damping, elapsedMs);
}
