import { describe, expect, it } from "vitest";
import { formatTickLabel, pickTickInterval } from "@/dashboard/timeline/utils/ticks";

describe("pickTickInterval", () => {
  it("picks a small interval at fine zoom levels", () => {
    expect(pickTickInterval(0.01, 1000, 80)).toBeLessThan(0.01);
  });

  it("picks a large interval at coarse zoom levels", () => {
    expect(pickTickInterval(3600, 800, 80)).toBeGreaterThanOrEqual(300);
  });

  it("returns the first preset for degenerate inputs", () => {
    expect(pickTickInterval(0, 100, 50)).toBe(0.000001);
    expect(pickTickInterval(10, 0, 50)).toBe(0.000001);
  });
});

describe("formatTickLabel", () => {
  it("uses µs / ms / s / m based on the interval", () => {
    expect(formatTickLabel(0.0005, 0.0001)).toMatch(/µs$/);
    expect(formatTickLabel(0.05, 0.01)).toMatch(/ms$/);
    expect(formatTickLabel(2, 1)).toMatch(/s$/);
    expect(formatTickLabel(125, 60)).toMatch(/m/);
  });

  it("returns em-dash for non-finite input", () => {
    expect(formatTickLabel(Number.NaN, 1)).toBe("—");
  });
});
