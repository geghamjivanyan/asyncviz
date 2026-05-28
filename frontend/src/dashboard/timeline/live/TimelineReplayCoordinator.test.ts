import { describe, expect, it } from "vitest";
import { TimelineDeltaProcessor } from "@/dashboard/timeline/live/TimelineDeltaProcessor";
import { TimelineInvalidationTracker } from "@/dashboard/timeline/live/TimelineInvalidation";
import { TimelineReplayCoordinator } from "@/dashboard/timeline/live/TimelineReplayCoordinator";
import {
  makeRuntimeEventEnvelope,
  makeTimelineDeltaEnvelope,
} from "@/dashboard/timeline/live/__fixtures__/mockEnvelopes";

function build() {
  const processor = new TimelineDeltaProcessor();
  const tracker = new TimelineInvalidationTracker();
  const coordinator = new TimelineReplayCoordinator({ processor, tracker });
  return { processor, tracker, coordinator };
}

describe("TimelineReplayCoordinator", () => {
  it("starts in idle mode", () => {
    const { coordinator } = build();
    expect(coordinator.currentMode()).toBe("idle");
    expect(coordinator.currentPhase()).toBe("idle");
  });

  it("transitions through replay → transitioning when applyReplayBatch runs", () => {
    const { coordinator, tracker } = build();
    coordinator.beginReplay();
    expect(coordinator.currentMode()).toBe("replay");
    const result = coordinator.applyReplayBatch([
      makeTimelineDeltaEnvelope({ sequence: 1, taskId: "t1" }),
      makeRuntimeEventEnvelope(2, "t2"),
    ]);
    expect(result.applied).toBe(2);
    expect(coordinator.currentPhase()).toBe("transitioning");
    const batch = tracker.drain();
    expect(batch.reasons).toContain("replay");
  });

  it("goLive flips back to live mode", () => {
    const { coordinator } = build();
    coordinator.beginReplay();
    coordinator.endReplay();
    coordinator.goLive();
    expect(coordinator.currentMode()).toBe("live");
  });

  it("aggregates stats across multiple replay batches", () => {
    const { coordinator } = build();
    coordinator.beginReplay();
    coordinator.applyReplayBatch([makeRuntimeEventEnvelope(1, "t1")]);
    coordinator.applyReplayBatch([
      makeRuntimeEventEnvelope(2, "t2"),
      makeRuntimeEventEnvelope(3, "t3"),
    ]);
    const m = coordinator.metrics();
    expect(m.replayBatchesApplied).toBe(2);
    expect(m.envelopesApplied).toBe(3);
  });
});
