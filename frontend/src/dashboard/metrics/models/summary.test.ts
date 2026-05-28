import { describe, expect, it } from "vitest";
import {
  WARNING_SEVERITY_RANK,
  emptySeverityCounts,
  highestSeverity,
  totalWarningCount,
} from "@/dashboard/metrics/models/summary";

describe("highestSeverity", () => {
  it("returns null when there are no warnings", () => {
    expect(highestSeverity(emptySeverityCounts())).toBeNull();
  });

  it("prefers critical over every other severity", () => {
    expect(highestSeverity({ info: 5, warning: 5, error: 5, critical: 1 })).toBe("critical");
  });

  it("falls back through error → warning → info", () => {
    expect(highestSeverity({ info: 0, warning: 0, error: 1, critical: 0 })).toBe("error");
    expect(highestSeverity({ info: 0, warning: 1, error: 0, critical: 0 })).toBe("warning");
    expect(highestSeverity({ info: 1, warning: 0, error: 0, critical: 0 })).toBe("info");
  });
});

describe("totalWarningCount", () => {
  it("sums every severity", () => {
    expect(totalWarningCount({ info: 1, warning: 2, error: 3, critical: 4 })).toBe(10);
  });

  it("handles missing fields safely", () => {
    expect(totalWarningCount(emptySeverityCounts())).toBe(0);
  });
});

describe("WARNING_SEVERITY_RANK", () => {
  it("is strictly increasing", () => {
    expect(WARNING_SEVERITY_RANK.info).toBeLessThan(WARNING_SEVERITY_RANK.warning);
    expect(WARNING_SEVERITY_RANK.warning).toBeLessThan(WARNING_SEVERITY_RANK.error);
    expect(WARNING_SEVERITY_RANK.error).toBeLessThan(WARNING_SEVERITY_RANK.critical);
  });
});
