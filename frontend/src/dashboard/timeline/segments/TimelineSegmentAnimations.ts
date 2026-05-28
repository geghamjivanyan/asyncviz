/**
 * Pure animation primitives for segment rendering.
 *
 * The renderer is intentionally non-animated today — every frame is
 * deterministic from camera + dataset. This module exposes the
 * minimal hooks the renderer will use once we land the running-pulse
 * + replay-flash transitions:
 *
 *   * a monotonic timestamp provider (injectable for tests),
 *   * easing helpers that respect ``prefers-reduced-motion``,
 *   * an oscillator that returns a stable [0..1] value over a
 *     configured period.
 *
 * Keeping the math pure means the eventual animated build-out lives
 * behind a single toggle without touching draw code.
 */

export type ClockFn = () => number;

const DEFAULT_PERIOD_MS = 1000;

/** Smoothstep ease — used for replay-flash fades. */
export function easeInOut(t: number): number {
  const clamped = Math.max(0, Math.min(1, t));
  return clamped * clamped * (3 - 2 * clamped);
}

/** Pure: sinusoidal [0..1] oscillator. */
export function oscillator(now: number, periodMs: number = DEFAULT_PERIOD_MS): number {
  if (!Number.isFinite(now) || periodMs <= 0) return 0;
  const phase = ((now % periodMs) + periodMs) % periodMs;
  return 0.5 + 0.5 * Math.sin((phase / periodMs) * Math.PI * 2);
}

/** Returns ``true`` when the runtime is asking for reduced motion. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return true;
  }
}

/** Stable animation phase resolver — disables animation when the user
 *  asked for reduced motion. */
export function animationPhase(args: {
  now: number;
  periodMs?: number;
  reducedMotion?: boolean;
}): number {
  if (args.reducedMotion ?? prefersReducedMotion()) return 0;
  return oscillator(args.now, args.periodMs ?? DEFAULT_PERIOD_MS);
}
