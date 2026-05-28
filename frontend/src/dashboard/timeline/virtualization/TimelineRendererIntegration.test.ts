/**
 * Integration smoke test — the virtualization engine attached to the
 * renderer culls rows + segments correctly per frame.
 */

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { TimelineVirtualizationEngine } from "@/dashboard/timeline/virtualization/TimelineVirtualizationEngine";
import { TimelineWindowMetrics } from "@/dashboard/timeline/virtualization/TimelineWindowMetrics";
import { installRowFakeCanvasContext } from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";
import type {
  TimelineRenderSegment,
  TimelineRow,
} from "@/dashboard/timeline/rendering/TimelineLayer";

let restoreCanvas: (() => void) | undefined;
beforeAll(() => {
  restoreCanvas = installRowFakeCanvasContext();
});
afterAll(() => {
  restoreCanvas?.();
});

function fakeRaf() {
  const queue: Array<{ id: number; cb: FrameRequestCallback }> = [];
  let next = 1;
  return {
    raf: (cb: FrameRequestCallback): number => {
      const id = next++;
      queue.push({ id, cb });
      return id;
    },
    caf: (id: number) => {
      const i = queue.findIndex((q) => q.id === id);
      if (i >= 0) queue.splice(i, 1);
    },
    flush: () => {
      const pending = queue.splice(0);
      pending.forEach((q) => q.cb(performance.now()));
    },
  };
}

describe("virtualization engine + renderer integration", () => {
  it("uses the virtualizer to cull rows + segments per frame", () => {
    const fake = fakeRaf();
    const metrics = new TimelineWindowMetrics();
    const engine = new TimelineVirtualizationEngine<TimelineRow, TimelineRenderSegment>({
      metrics,
    });
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 400, cssHeight: 80, devicePixelRatio: 1 });
    renderer.setCamera({ timeStart: 0, timeEnd: 5, rowStart: 0, rowHeight: 20 });
    renderer.setDataset({
      rows: Array.from({ length: 100 }, (_, i) => ({
        rowIndex: i,
        taskId: `t${i}`,
        label: `t${i}`,
      })),
      segments: Array.from({ length: 100 }, (_, i) => ({
        segmentId: `s${i}`,
        rowIndex: i,
        taskId: `t${i}`,
        startSeconds: i % 10,
        endSeconds: (i % 10) + 1,
        intent: "run" as const,
        isActive: false,
      })),
    });
    renderer.setVirtualizer(engine);
    fake.flush();
    const snap = metrics.snapshot();
    expect(snap.rowCulls).toBeGreaterThan(0);
    expect(snap.visibleRowsTotal).toBeGreaterThan(0);
    expect(snap.rowsCulledTotal).toBeGreaterThan(0);
  });

  it("invalidates the cache when setDataset advances the sequence", () => {
    const fake = fakeRaf();
    const engine = new TimelineVirtualizationEngine<TimelineRow, TimelineRenderSegment>();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 400, cssHeight: 80, devicePixelRatio: 1 });
    renderer.setCamera({ timeStart: 0, timeEnd: 5, rowStart: 0, rowHeight: 20 });
    renderer.setVirtualizer(engine);
    renderer.setDataset({
      rows: [{ rowIndex: 0, taskId: "a", label: "A" }],
      segments: [],
    });
    fake.flush();
    const seqAfterFirst = renderer.currentDatasetSequence();
    renderer.setDataset({
      rows: [
        { rowIndex: 0, taskId: "a", label: "A" },
        { rowIndex: 1, taskId: "b", label: "B" },
      ],
      segments: [],
    });
    fake.flush();
    expect(renderer.currentDatasetSequence()).toBeGreaterThan(seqAfterFirst);
  });
});
