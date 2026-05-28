import { describe, expect, it } from "vitest";
import {
  formatDuration,
  formatStartTime,
  formatTaskIdShort,
  formatWarningCount,
} from "@/dashboard/tasks/utils/format";

describe("formatDuration", () => {
  it("renders null / negative / non-finite as em-dash", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(-1)).toBe("—");
    expect(formatDuration(Number.NaN)).toBe("—");
  });

  it("scales the unit by magnitude", () => {
    expect(formatDuration(0.0005)).toMatch(/µs$/);
    expect(formatDuration(0.05)).toMatch(/ms$/);
    expect(formatDuration(2.5)).toMatch(/s$/);
    expect(formatDuration(95)).toMatch(/m/);
  });
});

describe("formatStartTime", () => {
  it("returns em-dash for null or non-finite", () => {
    expect(formatStartTime(null)).toBe("—");
    expect(formatStartTime(0)).toBe("—");
    expect(formatStartTime(Number.NaN)).toBe("—");
  });

  it("renders HH:MM:SS for a real epoch", () => {
    expect(formatStartTime(1)).toMatch(/^\d\d:\d\d:\d\d$/);
  });
});

describe("formatTaskIdShort", () => {
  it("returns em-dash for null or empty", () => {
    expect(formatTaskIdShort(null)).toBe("—");
    expect(formatTaskIdShort("")).toBe("—");
  });

  it("returns the id unchanged when short enough", () => {
    expect(formatTaskIdShort("abc")).toBe("abc");
  });

  it("shortens with a mid-ellipsis when long", () => {
    expect(formatTaskIdShort("abcdefghijklmnopqr")).toBe("abcdef…opqr");
  });
});

describe("formatWarningCount", () => {
  it("returns em-dash for zero", () => {
    expect(formatWarningCount(0)).toBe("—");
  });

  it("caps very large counts to 99+", () => {
    expect(formatWarningCount(150)).toBe("99+");
  });

  it("returns the literal count otherwise", () => {
    expect(formatWarningCount(5)).toBe("5");
  });
});
