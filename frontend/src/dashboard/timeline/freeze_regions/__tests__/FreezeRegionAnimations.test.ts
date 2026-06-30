import { describe, expect, it } from "vitest";
import {
  makePulseFn,
  PULSE_AMPLITUDE,
  PULSE_PERIOD_MS,
  pulseMultiplier,
} from "@/dashboard/timeline/freeze_regions/FreezeRegionAnimations";

describe("pulseMultiplier", () => {
  it("returns 1 when not active", () => {
    expect(pulseMultiplier(false, 0)).toBe(1);
    expect(pulseMultiplier(false, 12345)).toBe(1);
  });

  it("returns ≈1 at phase 0 (sin(0) = 0)", () => {
    expect(pulseMultiplier(true, 0)).toBeCloseTo(1);
  });

  it("hits the maximum amplitude at quarter-period", () => {
    expect(pulseMultiplier(true, PULSE_PERIOD_MS / 4)).toBeCloseTo(1 + PULSE_AMPLITUDE);
  });

  it("hits the minimum amplitude at three-quarter-period", () => {
    expect(pulseMultiplier(true, (3 * PULSE_PERIOD_MS) / 4)).toBeCloseTo(1 - PULSE_AMPLITUDE);
  });

  it("is replay-deterministic for the same nowMs", () => {
    const a = pulseMultiplier(true, 500);
    const b = pulseMultiplier(true, 500);
    expect(a).toBe(b);
  });

  it("returns 1 for non-finite clocks", () => {
    expect(pulseMultiplier(true, Number.NaN)).toBe(1);
    expect(pulseMultiplier(true, Number.POSITIVE_INFINITY)).toBe(1);
  });
});

describe("makePulseFn (reduced motion)", () => {
  it("collapses every call to 1 when reducedMotion is true", () => {
    const fn = makePulseFn(true);
    expect(fn(true, PULSE_PERIOD_MS / 4)).toBe(1);
    expect(fn(true, 0)).toBe(1);
  });

  it("returns the default pulse function otherwise", () => {
    const fn = makePulseFn(false);
    expect(fn(true, 0)).toBeCloseTo(1);
    expect(fn(true, PULSE_PERIOD_MS / 4)).toBeCloseTo(1 + PULSE_AMPLITUDE);
  });
});
