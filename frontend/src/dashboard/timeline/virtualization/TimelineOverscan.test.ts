import { describe, expect, it } from "vitest";
import {
  clampOverscan,
  resolveOverscan,
} from "@/dashboard/timeline/virtualization/TimelineOverscan";

describe("resolveOverscan", () => {
  it("returns the default overscan when no velocity is supplied", () => {
    const overscan = resolveOverscan({ visibleDurationSeconds: 10, visibleRowCount: 50 });
    expect(overscan.rowOverscan).toBeGreaterThanOrEqual(0);
    expect(overscan.timeOverscanSeconds).toBeGreaterThanOrEqual(0);
  });

  it("scales overscan with velocity", () => {
    const fast = resolveOverscan(
      {
        visibleDurationSeconds: 10,
        visibleRowCount: 50,
        panVelocitySeconds: 20,
        scrollVelocityRows: 100,
      },
      { velocityFactor: 0.5, maxRowOverscan: 128, maxTimeOverscanSeconds: 600 },
    );
    expect(fast.timeOverscanSeconds).toBeGreaterThanOrEqual(10);
    expect(fast.rowOverscan).toBeGreaterThanOrEqual(50);
  });

  it("clamps overscan to defensive maxima", () => {
    const overscan = resolveOverscan(
      {
        visibleDurationSeconds: 10,
        visibleRowCount: 50,
        panVelocitySeconds: 1e6,
        scrollVelocityRows: 1e6,
      },
      { velocityFactor: 1, maxRowOverscan: 32, maxTimeOverscanSeconds: 60 },
    );
    expect(overscan.rowOverscan).toBe(32);
    expect(overscan.timeOverscanSeconds).toBe(60);
  });

  it("clampOverscan clamps directly", () => {
    const clamped = clampOverscan(
      { rowOverscan: 999, timeOverscanSeconds: 999 },
      { maxRowOverscan: 5, maxTimeOverscanSeconds: 5 },
    );
    expect(clamped.rowOverscan).toBe(5);
    expect(clamped.timeOverscanSeconds).toBe(5);
  });
});
