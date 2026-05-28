import { describe, expect, it } from "vitest";
import {
  formatDurationMs,
  formatLagMs,
  formatPercent,
  formatSequence,
  formatWallTime,
} from "@/dashboard/connection/utils/format";

describe("formatLagMs", () => {
  it("returns em-dash for null / negative", () => {
    expect(formatLagMs(null)).toBe("—");
    expect(formatLagMs(-1)).toBe("—");
  });

  it("scales ms / s / m", () => {
    expect(formatLagMs(250)).toMatch(/ms$/);
    expect(formatLagMs(2500)).toMatch(/s$/);
    expect(formatLagMs(120_000)).toMatch(/m$/);
  });
});

describe("formatDurationMs", () => {
  it("renders sub-ms with two decimals", () => {
    expect(formatDurationMs(0.42)).toMatch(/ms$/);
  });

  it("renders large ms as seconds", () => {
    expect(formatDurationMs(1234)).toMatch(/s$/);
  });

  it("returns em-dash for non-finite / negative", () => {
    expect(formatDurationMs(Number.NaN)).toBe("—");
    expect(formatDurationMs(-1)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("clamps to 0-100", () => {
    expect(formatPercent(-1)).toBe("0%");
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(2)).toBe("100%");
  });
});

describe("formatSequence", () => {
  it("renders raw for small numbers", () => {
    expect(formatSequence(42)).toBe("42");
  });

  it("scales to k / M", () => {
    expect(formatSequence(2_500)).toMatch(/k$/);
    expect(formatSequence(2_500_000)).toMatch(/M$/);
  });

  it("returns em-dash for null", () => {
    expect(formatSequence(null)).toBe("—");
  });
});

describe("formatWallTime", () => {
  it("returns em-dash for invalid input", () => {
    expect(formatWallTime(0)).toBe("—");
    expect(formatWallTime(Number.NaN)).toBe("—");
  });

  it("renders HH:MM:SS for a real epoch ms", () => {
    expect(formatWallTime(1000)).toMatch(/^\d\d:\d\d:\d\d$/);
  });
});
