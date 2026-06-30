import { describe, expect, it } from "vitest";
import {
  batchIsActionable,
  batchIsActiveTickOnly,
  batchToRendererReason,
  coalesceRegions,
} from "@/dashboard/timeline/live/TimelineDirtyRegions";
import { EMPTY_INVALIDATION_BATCH } from "@/dashboard/timeline/live/models/TimelineLiveModels";

describe("TimelineDirtyRegions", () => {
  it("returns the empty batch sentinel for an empty iterable", () => {
    expect(coalesceRegions([])).toBe(EMPTY_INVALIDATION_BATCH);
  });

  it("collapses duplicate task / segment ids", () => {
    const batch = coalesceRegions([
      { reason: "row", taskIds: ["a", "b"], atMs: 0 },
      { reason: "row", taskIds: ["b", "c"], atMs: 0 },
      { reason: "segment", segmentIds: ["s1", "s2"], atMs: 0 },
      { reason: "segment", segmentIds: ["s2", "s3"], atMs: 0 },
    ]);
    expect([...batch.taskIds].sort()).toEqual(["a", "b", "c"]);
    expect([...batch.segmentIds].sort()).toEqual(["s1", "s2", "s3"]);
  });

  it("picks the highest sequence across regions", () => {
    const batch = coalesceRegions([
      { reason: "row", taskIds: ["a"], sequence: 5, atMs: 0 },
      { reason: "row", taskIds: ["b"], sequence: 10, atMs: 0 },
      { reason: "row", taskIds: ["c"], sequence: 2, atMs: 0 },
    ]);
    expect(batch.highestSequence).toBe(10);
  });

  it("batchIsActiveTickOnly detects pure animation flushes", () => {
    const batch = coalesceRegions([{ reason: "active-tick", atMs: 0 }]);
    expect(batchIsActiveTickOnly(batch)).toBe(true);
    const mixed = coalesceRegions([
      { reason: "active-tick", atMs: 0 },
      { reason: "row", taskIds: ["a"], atMs: 0 },
    ]);
    expect(batchIsActiveTickOnly(mixed)).toBe(false);
  });

  it("batchToRendererReason picks viewport > data > selection > camera", () => {
    expect(batchToRendererReason(coalesceRegions([{ reason: "viewport", atMs: 0 }]))).toBe(
      "viewport",
    );
    expect(batchToRendererReason(coalesceRegions([{ reason: "segment", atMs: 0 }]))).toBe("data");
    expect(batchToRendererReason(coalesceRegions([{ reason: "selection", atMs: 0 }]))).toBe(
      "selection",
    );
    expect(batchToRendererReason(coalesceRegions([{ reason: "active-tick", atMs: 0 }]))).toBe(
      "camera",
    );
  });

  it("batchIsActionable returns false for empty batches", () => {
    expect(batchIsActionable(EMPTY_INVALIDATION_BATCH)).toBe(false);
  });
});
