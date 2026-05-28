/**
 * Pulse-alpha helpers for active freeze regions.
 *
 * The renderer is fundamentally deterministic — every frame's output
 * is a pure function of (camera, viewport, regions, clock). For
 * animated overlays we feed the clock in explicitly so tests can drive
 * a stable phase.
 *
 * Pulse model: a slow sine wave (1.5 s period) modulates the body
 * alpha by ± :data:`PULSE_AMPLITUDE`. Anything > 1 is clamped down to
 * 1 so we don't blow the rgba range; anything < 0 clamps to 0.
 */

/** Period (ms) of one full pulse cycle. */
export const PULSE_PERIOD_MS = 1500;
/** Peak alpha modulation applied to the underlying alpha. */
export const PULSE_AMPLITUDE = 0.18;

/** Stable pulse multiplier for ``nowMs``. Returns 1 outside an active state. */
export function pulseMultiplier(active: boolean, nowMs: number): number {
  if (!active) return 1;
  if (!Number.isFinite(nowMs)) return 1;
  const phase = (nowMs % PULSE_PERIOD_MS) / PULSE_PERIOD_MS;
  // sin wave centered on 1, with amplitude PULSE_AMPLITUDE
  return 1 + Math.sin(phase * 2 * Math.PI) * PULSE_AMPLITUDE;
}

/** Reduced-motion adapter — collapses any pulse to a steady 1. */
export function makePulseFn(reducedMotion: boolean): (active: boolean, nowMs: number) => number {
  if (reducedMotion) return () => 1;
  return pulseMultiplier;
}
