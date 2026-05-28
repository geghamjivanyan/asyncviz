import { describe, expect, it } from "vitest";
import {
  formatCategory,
  formatEventDuration,
  formatEventTime,
  formatTaskIdCompact,
} from "@/dashboard/events/utils/format";

describe("formatCategory", () => {
  it("maps every category to a short label", () => {
    expect(formatCategory("task.created")).toBe("created");
    expect(formatCategory("task.started")).toBe("started");
    expect(formatCategory("task.failed")).toBe("failed");
  });
});

describe("formatEventTime", () => {
  it("returns em-dash for invalid input", () => {
    expect(formatEventTime(0)).toBe("—");
    expect(formatEventTime(-1)).toBe("—");
    expect(formatEventTime(Number.NaN)).toBe("—");
  });

  it("renders HH:MM:SS.mmm for a real epoch", () => {
    expect(formatEventTime(1)).toMatch(/^\d\d:\d\d:\d\d\.\d{3}$/);
  });
});

describe("formatEventDuration", () => {
  it("returns empty string for null / negative / non-finite", () => {
    expect(formatEventDuration(null)).toBe("");
    expect(formatEventDuration(-1)).toBe("");
    expect(formatEventDuration(Number.NaN)).toBe("");
  });

  it("scales the unit by magnitude", () => {
    expect(formatEventDuration(0.0005)).toMatch(/µs$/);
    expect(formatEventDuration(0.05)).toMatch(/ms$/);
    expect(formatEventDuration(2.5)).toMatch(/s$/);
  });
});

describe("formatTaskIdCompact", () => {
  it("returns short ids unchanged", () => {
    expect(formatTaskIdCompact("abc")).toBe("abc");
  });

  it("shortens long ids with a mid-ellipsis", () => {
    expect(formatTaskIdCompact("abcdefghijklmnop")).toBe("abcdef…mnop");
  });
});
