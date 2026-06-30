import { describe, expect, it } from "vitest";
import { TimelinePanMomentum, decayVelocity } from "@/dashboard/timeline/pan/TimelinePanMomentum";

describe("TimelinePanMomentum", () => {
  it("velocity is zero when no samples are recorded", () => {
    const m = new TimelinePanMomentum();
    expect(m.velocity(100)).toBe(0);
  });

  it("averages sample deltas across the window", () => {
    const m = new TimelinePanMomentum({ windowMs: 100 });
    m.push({ deltaSeconds: 1, deltaMs: 10, atMs: 100 });
    m.push({ deltaSeconds: 1, deltaMs: 10, atMs: 110 });
    expect(m.velocity(120)).toBeCloseTo(0.1);
  });

  it("drops samples outside the window", () => {
    const m = new TimelinePanMomentum({ windowMs: 50 });
    m.push({ deltaSeconds: 5, deltaMs: 10, atMs: 0 });
    m.push({ deltaSeconds: 1, deltaMs: 10, atMs: 200 });
    // At t=210, only the t=200 sample is inside the window
    expect(m.velocity(210)).toBeCloseTo(0.1);
  });

  it("reset clears samples", () => {
    const m = new TimelinePanMomentum();
    m.push({ deltaSeconds: 1, deltaMs: 1, atMs: 0 });
    m.reset();
    expect(m.size()).toBe(0);
    expect(m.velocity(0)).toBe(0);
  });

  it("decayVelocity reduces the velocity exponentially", () => {
    const initial = 1;
    const decayed = decayVelocity(initial, 100, 0.01);
    expect(decayed).toBeGreaterThan(0);
    expect(decayed).toBeLessThan(initial);
  });

  it("decayVelocity returns the input when decayPerMs is zero", () => {
    expect(decayVelocity(2, 100, 0)).toBe(2);
  });
});
