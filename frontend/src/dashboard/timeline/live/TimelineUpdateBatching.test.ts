import { describe, expect, it, vi } from "vitest";
import { TimelineUpdateBatcher } from "@/dashboard/timeline/live/TimelineUpdateBatching";

describe("TimelineUpdateBatcher", () => {
  it("coalesces multiple schedule() calls into one microtask flush", async () => {
    const flush = vi.fn();
    const microtaskQueue: Array<() => void> = [];
    const batcher = new TimelineUpdateBatcher(flush, {
      queueMicrotask: (cb) => microtaskQueue.push(cb),
    });
    batcher.schedule();
    batcher.schedule();
    batcher.schedule();
    expect(flush).not.toHaveBeenCalled();
    expect(batcher.metrics().batchesScheduled).toBe(1);
    expect(batcher.metrics().batchesCoalesced).toBe(2);
    microtaskQueue.forEach((cb) => cb());
    expect(flush).toHaveBeenCalledTimes(1);
    expect(batcher.metrics().batchesFlushed).toBe(1);
  });

  it("supports rAF strategy with injectable raf", () => {
    const flush = vi.fn();
    const queue: FrameRequestCallback[] = [];
    const batcher = new TimelineUpdateBatcher(flush, {
      strategy: "raf",
      raf: (cb) => {
        queue.push(cb);
        return queue.length;
      },
      caf: () => {},
    });
    batcher.schedule();
    batcher.schedule();
    expect(flush).not.toHaveBeenCalled();
    queue.forEach((cb) => cb(0));
    expect(flush).toHaveBeenCalledTimes(1);
  });

  it("flushNow() bypasses the batching window and clears pending state", () => {
    const flush = vi.fn();
    const microtaskQueue: Array<() => void> = [];
    const batcher = new TimelineUpdateBatcher(flush, {
      queueMicrotask: (cb) => microtaskQueue.push(cb),
    });
    batcher.schedule();
    batcher.flushNow();
    expect(flush).toHaveBeenCalledTimes(1);
    microtaskQueue.forEach((cb) => cb());
    expect(flush).toHaveBeenCalledTimes(1);
  });

  it("dispose cancels any pending flush", () => {
    const flush = vi.fn();
    const queue: FrameRequestCallback[] = [];
    const batcher = new TimelineUpdateBatcher(flush, {
      strategy: "raf",
      raf: (cb) => {
        queue.push(cb);
        return queue.length;
      },
      caf: () => {
        queue.length = 0;
      },
    });
    batcher.schedule();
    batcher.dispose();
    // The cancel handler emptied the queue; nothing to fire.
    queue.forEach((cb) => cb(0));
    expect(flush).not.toHaveBeenCalled();
  });
});
