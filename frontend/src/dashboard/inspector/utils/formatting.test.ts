import { describe, expect, it } from "vitest";
import {
  formatDuration,
  formatLifecycleState,
  formatPercent,
  formatSequence,
  formatWallTime,
  severityIntent,
  shortenIdentifier,
} from "@/dashboard/inspector/utils/formatting";

describe("inspector formatting", () => {
  it("formatDuration handles sub-µs / ms / s / m+s tiers", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(-1)).toBe("—");
    expect(formatDuration(NaN)).toBe("—");
    expect(formatDuration(0)).toBe("0µs");
    expect(formatDuration(0.0001)).toBe("100µs");
    expect(formatDuration(0.05)).toBe("50.0ms");
    expect(formatDuration(2)).toBe("2.00s");
    expect(formatDuration(125)).toBe("2m05s");
  });

  it("formatPercent renders integer percentages", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(1)).toBe("100%");
  });

  it("formatWallTime renders ISO for wall-clock values", () => {
    expect(formatWallTime(null)).toBe("—");
    expect(formatWallTime(1)).toBe("1.000s");
    const wall = formatWallTime(1_700_000_000);
    expect(wall.endsWith("Z")).toBe(true);
  });

  it("formatLifecycleState capitalizes known states", () => {
    expect(formatLifecycleState("running")).toBe("Running");
    expect(formatLifecycleState("failed")).toBe("Failed");
    expect(formatLifecycleState("unknown")).toBe("Unknown");
  });

  it("shortenIdentifier abbreviates long ids", () => {
    expect(shortenIdentifier("short")).toBe("short");
    expect(shortenIdentifier("aaaaaaaaaaaaaabbbbbb")).toBe("aaaaaa…bbbb");
  });

  it("formatSequence inserts thousands separators", () => {
    expect(formatSequence(null)).toBe("—");
    expect(formatSequence(1234567)).toBe(Number(1234567).toLocaleString());
  });

  it("severityIntent maps severities to intent tokens", () => {
    expect(severityIntent("critical")).toBe("danger");
    expect(severityIntent("error")).toBe("danger");
    expect(severityIntent("warning")).toBe("warning");
    expect(severityIntent("info")).toBe("accent");
    expect(severityIntent(null)).toBe("default");
  });
});
