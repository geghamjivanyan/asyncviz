import { describe, expect, it } from "vitest";
import {
  formatCount,
  formatLagMs,
  formatPercent,
  formatRate,
  formatSequence,
  formatUptime,
} from "@/dashboard/metrics/utils/format";

describe("formatRate", () => {
  it("returns 0/s for zero / non-finite", () => {
    expect(formatRate(0)).toBe("0/s");
    expect(formatRate(Number.NaN)).toBe("0/s");
    expect(formatRate(-1)).toBe("0/s");
  });

  it("renders small values with 2 decimals", () => {
    expect(formatRate(1.234)).toBe("1.23/s");
  });

  it("scales to k/s for high rates", () => {
    expect(formatRate(15_000)).toMatch(/k\/s$/);
  });
});

describe("formatCount", () => {
  it("returns 0 for non-finite", () => {
    expect(formatCount(Number.NaN)).toBe("0");
  });

  it("renders raw for small values", () => {
    expect(formatCount(42)).toBe("42");
  });

  it("scales to k / M for large values", () => {
    expect(formatCount(2_500)).toMatch(/k$/);
    expect(formatCount(5_500_000)).toMatch(/M$/);
  });
});

describe("formatUptime", () => {
  it("returns 0s for negative / zero", () => {
    expect(formatUptime(0)).toBe("0s");
    expect(formatUptime(-1)).toBe("0s");
  });

  it("scales seconds → minutes → hours → days", () => {
    expect(formatUptime(45)).toBe("45s");
    expect(formatUptime(125)).toMatch(/^2m/);
    expect(formatUptime(3700)).toMatch(/^1h/);
    expect(formatUptime(90_000)).toMatch(/^1d/);
  });
});

describe("formatLagMs", () => {
  it("returns em-dash for null / negative", () => {
    expect(formatLagMs(null)).toBe("—");
    expect(formatLagMs(-1)).toBe("—");
  });

  it("scales to ms / s / m", () => {
    expect(formatLagMs(450)).toMatch(/ms$/);
    expect(formatLagMs(2500)).toMatch(/s$/);
    expect(formatLagMs(120_000)).toMatch(/m$/);
  });
});

describe("formatPercent", () => {
  it("clamps to 0-100", () => {
    expect(formatPercent(-5)).toBe("0%");
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(2)).toBe("100%");
  });
});

describe("formatSequence", () => {
  it("returns em-dash for null", () => {
    expect(formatSequence(null)).toBe("—");
  });

  it("delegates to formatCount", () => {
    expect(formatSequence(42)).toBe("42");
    expect(formatSequence(15_000)).toMatch(/k$/);
  });
});
