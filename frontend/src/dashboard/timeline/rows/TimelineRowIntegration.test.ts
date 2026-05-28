/**
 * Integration smoke test: the row renderer slotted into the scene
 * graph receives correctly-culled rows and emits row metrics. Uses
 * the row package's richer canvas mock + a manual rAF scheduler.
 */

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { TimelineRowRenderer } from "@/dashboard/timeline/rows/TimelineRowRenderer";
import {
  TimelineRowMetrics,
  resetTimelineRowMetrics,
} from "@/dashboard/timeline/rows/TimelineRowMetrics";
import { installRowFakeCanvasContext } from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";
import { resetTimelineRendererMetrics } from "@/dashboard/timeline/observability";

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

describe("row renderer integration", () => {
  it("renders rows + reports metrics when wired into TimelineRenderer", () => {
    resetTimelineRowMetrics();
    resetTimelineRendererMetrics();
    const fake = fakeRaf();
    const metrics = new TimelineRowMetrics();
    const rowCtrl = new TimelineRowRenderer({ metrics });
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 400, cssHeight: 80, devicePixelRatio: 2 });
    renderer.setCamera({ timeStart: 0, timeEnd: 5, rowStart: 0, rowHeight: 22 });
    renderer.setDataset({
      rows: [
        {
          rowIndex: 0,
          taskId: "a",
          label: "Task A",
          state: "running",
          coroutineName: "fn_a",
          warningSeverity: null,
          warningCount: 0,
        },
        {
          rowIndex: 1,
          taskId: "b",
          label: "Task B",
          state: "waiting",
          coroutineName: "fn_b",
          warningSeverity: "warning",
          warningCount: 2,
        },
      ],
      segments: [],
    });
    renderer.addLayer(rowCtrl.background);
    renderer.addLayer(rowCtrl.foreground);
    fake.flush();
    const snap = metrics.snapshot();
    expect(snap.rowsRendered).toBeGreaterThan(0);
    expect(snap.warningsRendered).toBe(1);
  });

  it("upscales the backing canvas to HiDPI without changing CSS coords", () => {
    const fake = fakeRaf();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 200, cssHeight: 100, devicePixelRatio: 2 });
    renderer.setCamera({ timeStart: 0, timeEnd: 5, rowStart: 0, rowHeight: 22 });
    fake.flush();
    expect(canvas.width).toBe(400);
    expect(canvas.height).toBe(200);
  });
});
