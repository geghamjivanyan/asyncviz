import { describe, expect, it } from "vitest";
import {
  createRateTracker,
  rateFromTracker,
  recordRateSample,
} from "@/dashboard/metrics/models/rateTracker";

describe("rateTracker", () => {
  it("returns 0 when no samples", () => {
    const tracker = createRateTracker();
    expect(rateFromTracker(tracker, 1000)).toBe(0);
  });

  it("returns 0 with a single sample", () => {
    let t = createRateTracker();
    t = recordRateSample(t, 5, 1000);
    expect(rateFromTracker(t, 1500)).toBe(0);
  });

  it("computes a positive rate from two samples", () => {
    let t = createRateTracker({ windowMs: 10_000 });
    t = recordRateSample(t, 0, 0);
    t = recordRateSample(t, 10, 1000);
    expect(rateFromTracker(t, 1000)).toBeCloseTo(10);
  });

  it("ignores stale samples outside the window", () => {
    let t = createRateTracker({ windowMs: 1000 });
    t = recordRateSample(t, 0, 0);
    t = recordRateSample(t, 100, 2000);
    // Window cutoff = 2000 - 1000 = 1000; first sample is dropped.
    // Only one sample remains — rate must be 0.
    expect(rateFromTracker(t, 2000)).toBe(0);
  });

  it("does not regress when total decreases (e.g. counter reset)", () => {
    let t = createRateTracker({ windowMs: 10_000 });
    t = recordRateSample(t, 100, 0);
    t = recordRateSample(t, 50, 1000);
    expect(rateFromTracker(t, 1000)).toBe(0);
  });

  it("caps the buffer at the capacity", () => {
    let t = createRateTracker({ capacity: 3 });
    for (let i = 0; i < 10; i += 1) {
      t = recordRateSample(t, i, i * 100);
    }
    expect(t.samples.length).toBeLessThanOrEqual(3);
  });
});
