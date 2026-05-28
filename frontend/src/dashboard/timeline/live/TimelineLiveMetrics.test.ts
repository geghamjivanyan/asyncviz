import { describe, expect, it } from "vitest";
import { TimelineLiveMetrics } from "@/dashboard/timeline/live/TimelineLiveMetrics";

describe("TimelineLiveMetrics", () => {
  it("counts envelopes + invalidations by reason", () => {
    const metrics = new TimelineLiveMetrics();
    metrics.recordEnvelope(false);
    metrics.recordEnvelope(true);
    metrics.recordInvalidation("row");
    metrics.recordInvalidation("segment");
    metrics.recordInvalidation("row");
    const snap = metrics.snapshot();
    expect(snap.envelopesObserved).toBe(2);
    expect(snap.envelopesSuppressed).toBe(1);
    expect(snap.invalidationsByReason.row).toBe(2);
    expect(snap.invalidationsByReason.segment).toBe(1);
  });

  it("tracks batch latency + max + total", () => {
    const metrics = new TimelineLiveMetrics();
    metrics.recordBatch(3, 4, 100);
    metrics.recordBatch(2, 10, 200);
    metrics.recordBatch(1, 7, 300);
    const snap = metrics.snapshot();
    expect(snap.batchesEmitted).toBe(3);
    expect(snap.lastBatchLatencyMs).toBe(7);
    expect(snap.maxBatchLatencyMs).toBe(10);
    expect(snap.totalBatchLatencyMs).toBe(21);
    expect(snap.batchRegionsCoalesced).toBe(6);
    expect(snap.lastFlushAtMs).toBe(300);
  });

  it("tracks active ticks + suppressions separately", () => {
    const metrics = new TimelineLiveMetrics();
    metrics.recordActiveTick(false);
    metrics.recordActiveTick(false);
    metrics.recordActiveTick(true);
    const snap = metrics.snapshot();
    expect(snap.activeTicks).toBe(2);
    expect(snap.activeTicksSuppressed).toBe(1);
  });

  it("tracks mode transitions", () => {
    const metrics = new TimelineLiveMetrics();
    metrics.setMode("live");
    expect(metrics.snapshot().currentMode).toBe("live");
    metrics.setMode("replay");
    expect(metrics.snapshot().currentMode).toBe("replay");
  });

  it("reset clears every counter", () => {
    const metrics = new TimelineLiveMetrics();
    metrics.recordEnvelope(false);
    metrics.recordBatch(1, 1, 1);
    metrics.recordReplayBatch(2);
    metrics.reset();
    const snap = metrics.snapshot();
    expect(snap.envelopesObserved).toBe(0);
    expect(snap.batchesEmitted).toBe(0);
    expect(snap.replayBatchesApplied).toBe(0);
  });
});
