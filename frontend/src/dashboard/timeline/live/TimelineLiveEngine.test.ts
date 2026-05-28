import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { TimelineLiveEngine } from "@/dashboard/timeline/live/TimelineLiveEngine";
import { TimelineLiveMetrics } from "@/dashboard/timeline/live/TimelineLiveMetrics";
import { TimelineRenderer } from "@/dashboard/timeline/rendering/TimelineRenderer";
import { installRowFakeCanvasContext } from "@/dashboard/timeline/rows/__fixtures__/mockCanvas";
import {
  makeHeartbeatEnvelope,
  makeRuntimeEventEnvelope,
  makeTimelineDeltaEnvelope,
} from "@/dashboard/timeline/live/__fixtures__/mockEnvelopes";

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

function setupEngine(): {
  engine: TimelineLiveEngine;
  metrics: TimelineLiveMetrics;
  renderer: TimelineRenderer;
  rendererRaf: ReturnType<typeof fakeRaf>;
  microtasks: Array<() => void>;
  animationRaf: ReturnType<typeof fakeRaf>;
  flushMicrotasks(): void;
} {
  const rendererRaf = fakeRaf();
  const animationRaf = fakeRaf();
  const microtasks: Array<() => void> = [];
  const metrics = new TimelineLiveMetrics();
  const renderer = new TimelineRenderer({
    scheduler: { raf: rendererRaf.raf, caf: rendererRaf.caf },
  });
  const engine = new TimelineLiveEngine({
    renderer,
    metrics,
    batching: { queueMicrotask: (cb) => microtasks.push(cb) },
    animation: { raf: animationRaf.raf, caf: animationRaf.caf },
  });
  const flushMicrotasks = () => {
    const pending = microtasks.splice(0);
    pending.forEach((cb) => cb());
  };
  return { engine, metrics, renderer, rendererRaf, microtasks, animationRaf, flushMicrotasks };
}

describe("TimelineLiveEngine", () => {
  it("flushes a single batch when multiple deltas arrive in one window", () => {
    const { engine, metrics, rendererRaf, flushMicrotasks } = setupEngine();
    engine.processEnvelope(makeTimelineDeltaEnvelope({ sequence: 1, taskId: "t1" }));
    engine.processEnvelope(makeTimelineDeltaEnvelope({ sequence: 2, taskId: "t1" }));
    engine.processEnvelope(makeRuntimeEventEnvelope(3, "t2"));
    flushMicrotasks();
    // Each delta schedules a flush but they coalesce into one frame
    // request on the renderer.
    const snap = metrics.snapshot();
    expect(snap.batchesEmitted).toBe(1);
    expect(snap.flushesExecuted).toBe(1);
    expect(snap.liveEnvelopesApplied).toBe(3);
    // Renderer's scheduler picked up the invalidation.
    rendererRaf.flush();
  });

  it("no-ops heartbeat envelopes — no flush, no envelope count", () => {
    const { engine, metrics, flushMicrotasks } = setupEngine();
    engine.processEnvelope(makeHeartbeatEnvelope());
    flushMicrotasks();
    expect(metrics.snapshot().batchesEmitted).toBe(0);
    expect(metrics.snapshot().envelopesObserved).toBe(1);
  });

  it("replay batches flush synchronously + record replay metrics", () => {
    const { engine, metrics } = setupEngine();
    engine.processReplayBatch([
      makeRuntimeEventEnvelope(1, "t1"),
      makeRuntimeEventEnvelope(2, "t2"),
      makeTimelineDeltaEnvelope({ sequence: 3, taskId: "t1" }),
    ]);
    const snap = metrics.snapshot();
    expect(snap.replayBatchesApplied).toBe(1);
    expect(snap.replayEnvelopesApplied).toBe(3);
    expect(snap.invalidationsByReason.replay).toBeGreaterThan(0);
    expect(snap.batchesEmitted).toBe(1);
  });

  it("active-segment count drives the animation clock + emits camera invalidations", () => {
    const { engine, metrics, animationRaf, flushMicrotasks } = setupEngine();
    engine.setActiveSegmentCount(2);
    animationRaf.flush();
    flushMicrotasks();
    const snap = metrics.snapshot();
    expect(snap.activeTicks).toBe(1);
    expect(snap.invalidationsByReason["active-tick"]).toBe(1);
    engine.setActiveSegmentCount(0);
    animationRaf.flush();
    expect(metrics.snapshot().activeTicks).toBe(1);
  });

  it("invalidateAll pushes a viewport region", () => {
    const { engine, metrics, flushMicrotasks } = setupEngine();
    engine.invalidateAll();
    flushMicrotasks();
    const snap = metrics.snapshot();
    expect(snap.invalidationsByReason.viewport).toBe(1);
    expect(snap.batchesEmitted).toBe(1);
  });

  it("invalidateRow + invalidateSegment record the right reasons", () => {
    const { engine, metrics, flushMicrotasks } = setupEngine();
    engine.invalidateRow("t1");
    engine.invalidateSegment("s1", "t1");
    flushMicrotasks();
    const snap = metrics.snapshot();
    expect(snap.invalidationsByReason.row).toBe(1);
    expect(snap.invalidationsByReason.segment).toBe(1);
  });

  it("mode reflects pause / resume", () => {
    const { engine } = setupEngine();
    expect(engine.mode()).toBe("live");
    engine.pause();
    expect(engine.mode()).toBe("paused");
    engine.resume();
    expect(engine.mode()).toBe("live");
  });

  it("dispose halts scheduling", () => {
    const { engine, flushMicrotasks, metrics } = setupEngine();
    engine.dispose();
    engine.processEnvelope(makeRuntimeEventEnvelope(1, "t1"));
    flushMicrotasks();
    expect(metrics.snapshot().batchesEmitted).toBe(0);
  });
});
