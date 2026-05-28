import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { buildReplayTimelineDiagnostics } from "@/dashboard/replay/diagnostics/ReplayTimelineDiagnostics";
import {
  recordSeekChange,
  resetReplayTimelineMetrics,
} from "@/dashboard/replay/diagnostics/ReplayTimelineMetrics";
import {
  clearReplayTimelineTrace,
  recordReplayTimelineTrace,
  setReplayTimelineTraceEnabled,
} from "@/dashboard/replay/diagnostics/ReplayTimelineTracing";

const baseStats = {
  playbackUpdatesApplied: 0,
  markersAppended: 0,
  bookmarksAdded: 0,
  scrubEvents: 0,
  seeksRequested: 0,
};

beforeEach(() => {
  resetReplayTimelineMetrics();
  clearReplayTimelineTrace();
});

afterEach(() => {
  setReplayTimelineTraceEnabled(false);
});

describe("buildReplayTimelineDiagnostics", () => {
  it("returns counters + trace tail", () => {
    setReplayTimelineTraceEnabled(true);
    recordSeekChange(50);
    recordReplayTimelineTrace("seek-completed", "ok");
    const diag = buildReplayTimelineDiagnostics(baseStats);
    expect(diag.metrics.cumulativeSeekLatencyMs).toBe(50);
    expect(diag.traceEnabled).toBe(true);
    expect(diag.recentTrace).toHaveLength(1);
    expect(diag.recentTrace[0].kind).toBe("seek-completed");
  });

  it("respects trace limit", () => {
    setReplayTimelineTraceEnabled(true);
    for (let i = 0; i < 50; i += 1) {
      recordReplayTimelineTrace("seek-completed", String(i));
    }
    const diag = buildReplayTimelineDiagnostics(baseStats, 10);
    expect(diag.recentTrace).toHaveLength(10);
  });
});
