/**
 * Integration smoke test — segment renderer slotted into the scene
 * graph receives correctly-culled segments and emits segment metrics.
 */

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { TimelineSegmentRenderer } from "@/dashboard/timeline/segments/TimelineSegmentRenderer";
import {
  TimelineSegmentMetrics,
  resetTimelineSegmentMetrics,
} from "@/dashboard/timeline/segments/TimelineSegmentMetrics";
import { installRowFakeCanvasContext } from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";
import { resetTimelineRendererMetrics } from "@/dashboard/timeline/observability";
import { makeRenderSegment } from "@/dashboard/timeline/segments/__fixtures__/makeSegment";

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

describe("segment renderer integration", () => {
  it("renders segments + reports metrics when wired into TimelineRenderer", () => {
    resetTimelineSegmentMetrics();
    resetTimelineRendererMetrics();
    const fake = fakeRaf();
    const metrics = new TimelineSegmentMetrics();
    const segmentLayer = new TimelineSegmentRenderer({ metrics });
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 400, cssHeight: 80, devicePixelRatio: 2 });
    renderer.setCamera({ timeStart: 0, timeEnd: 5, rowStart: 0, rowHeight: 22 });
    renderer.setDataset({
      rows: [{ rowIndex: 0, taskId: "a", label: "A" }],
      segments: [
        makeRenderSegment("s1", 0, 1, 2, { lifecycleState: "running" }),
        makeRenderSegment("s2", 0, 3, 4, { lifecycleState: "waiting" }),
      ],
    });
    renderer.addLayer(segmentLayer);
    fake.flush();
    const snap = metrics.snapshot();
    expect(snap.segmentsRendered).toBeGreaterThan(0);
  });
});
