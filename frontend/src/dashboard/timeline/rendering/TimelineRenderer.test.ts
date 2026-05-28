/**
 * Renderer integration tests.
 *
 * The renderer uses a real HTMLCanvasElement (jsdom). We don't assert
 * on the produced pixels — only that:
 *
 *   * frames are scheduled deterministically,
 *   * layers receive the correct render context,
 *   * culled rows/segments reach the layers,
 *   * resize + camera updates trigger invalidation.
 */

import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import type { RenderContext, TimelineLayer } from "@/dashboard/timeline/rendering/TimelineLayer";
import { installFakeCanvasContext } from "@/dashboard/timeline/rendering/__fixtures__/mockCanvas";

let restoreCanvas: (() => void) | undefined;
beforeAll(() => {
  restoreCanvas = installFakeCanvasContext();
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

function tracerLayer(): { layer: TimelineLayer; received: RenderContext[] } {
  const received: RenderContext[] = [];
  return {
    layer: {
      id: "tracer",
      order: 0,
      enabled: true,
      render: (ctx) => {
        received.push(ctx);
      },
    },
    received,
  };
}

describe("TimelineRenderer", () => {
  it("renders a frame after invalidation when a canvas is attached", () => {
    const fake = fakeRaf();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 200, cssHeight: 100, devicePixelRatio: 1 });
    renderer.setCamera({ timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 18 });
    const { layer, received } = tracerLayer();
    renderer.addLayer(layer);
    fake.flush();
    expect(received.length).toBeGreaterThan(0);
  });

  it("forwards visible rows + segments to layers", () => {
    const fake = fakeRaf();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 200, cssHeight: 100, devicePixelRatio: 1 });
    renderer.setCamera({ timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 });
    renderer.setDataset({
      rows: [
        { rowIndex: 0, taskId: "a", label: "A" },
        { rowIndex: 1, taskId: "b", label: "B" },
      ],
      segments: [
        {
          segmentId: "s1",
          rowIndex: 0,
          taskId: "a",
          startSeconds: 2,
          endSeconds: 5,
          intent: "run",
          isActive: false,
        },
        // out of viewport
        {
          segmentId: "s2",
          rowIndex: 0,
          taskId: "a",
          startSeconds: 200,
          endSeconds: 250,
          intent: "run",
          isActive: false,
        },
      ],
    });
    const { layer, received } = tracerLayer();
    renderer.addLayer(layer);
    fake.flush();
    expect(received.length).toBeGreaterThan(0);
    const scene = received[received.length - 1]!.scene;
    expect(scene.rows.length).toBe(2);
    expect(scene.segments.length).toBe(1);
    expect(scene.segments[0]!.segmentId).toBe("s1");
  });

  it("does not render with a zero-size viewport", () => {
    const fake = fakeRaf();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 0, cssHeight: 0, devicePixelRatio: 1 });
    const { layer, received } = tracerLayer();
    renderer.addLayer(layer);
    fake.flush();
    expect(received).toEqual([]);
  });

  it("setSelectedTaskId triggers an invalidation", () => {
    const fake = fakeRaf();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 200, cssHeight: 100, devicePixelRatio: 1 });
    renderer.setCamera({ timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 });
    fake.flush();
    const beforeFrames = renderer.internalState().framesRendered;
    renderer.setSelectedTaskId("t1");
    fake.flush();
    expect(renderer.internalState().framesRendered).toBeGreaterThan(beforeFrames);
  });

  it("records frame timings into observability", () => {
    const fake = fakeRaf();
    const renderer = new TimelineRenderer({ scheduler: { raf: fake.raf, caf: fake.caf } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.setViewport({ cssWidth: 200, cssHeight: 100, devicePixelRatio: 1 });
    renderer.setCamera({ timeStart: 0, timeEnd: 10, rowStart: 0, rowHeight: 20 });
    const before = renderer.rendererMetrics().snapshot();
    fake.flush();
    const after = renderer.rendererMetrics().snapshot();
    expect(after.framesRendered).toBeGreaterThan(before.framesRendered);
  });

  it("can attach + detach the canvas safely", () => {
    const renderer = new TimelineRenderer({ scheduler: { raf: vi.fn(), caf: vi.fn() } });
    const canvas = document.createElement("canvas");
    renderer.attachCanvas(canvas);
    renderer.attachCanvas(null);
    renderer.dispose();
  });
});
