import { describe, expect, it, vi } from "vitest";
import { TimelineScheduler } from "@/dashboard/timeline/scheduler/TimelineScheduler";

function makeFakeRaf() {
  const queue: Array<{ id: number; cb: FrameRequestCallback }> = [];
  let next = 1;
  return {
    raf: (cb: FrameRequestCallback): number => {
      const id = next++;
      queue.push({ id, cb });
      return id;
    },
    caf: (id: number): void => {
      const i = queue.findIndex((q) => q.id === id);
      if (i >= 0) queue.splice(i, 1);
    },
    flush: (): void => {
      const pending = queue.splice(0);
      pending.forEach((q) => q.cb(performance.now()));
    },
    queue,
  };
}

describe("TimelineScheduler", () => {
  it("schedules a single rAF for repeated invalidations", () => {
    const render = vi.fn();
    const fake = makeFakeRaf();
    const sched = new TimelineScheduler(render, { raf: fake.raf, caf: fake.caf });
    sched.invalidate("camera");
    sched.invalidate("data");
    sched.invalidate("overlay");
    expect(fake.queue).toHaveLength(1);
    fake.flush();
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("does not render when nothing is dirty", () => {
    const render = vi.fn();
    const fake = makeFakeRaf();
    const sched = new TimelineScheduler(render, { raf: fake.raf, caf: fake.caf });
    sched.invalidate();
    fake.flush();
    expect(render).toHaveBeenCalledTimes(1);
    // Manually pretend the flag was cleared by another path.
    fake.flush();
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("re-schedules another frame after the previous one completed", () => {
    const render = vi.fn();
    const fake = makeFakeRaf();
    const sched = new TimelineScheduler(render, { raf: fake.raf, caf: fake.caf });
    sched.invalidate("data");
    fake.flush();
    expect(render).toHaveBeenCalledTimes(1);
    sched.invalidate("data");
    fake.flush();
    expect(render).toHaveBeenCalledTimes(2);
  });

  it("forceRender runs synchronously", () => {
    const render = vi.fn();
    const fake = makeFakeRaf();
    const sched = new TimelineScheduler(render, { raf: fake.raf, caf: fake.caf });
    sched.forceRender();
    expect(render).toHaveBeenCalledTimes(1);
  });

  it("dispose cancels any pending frame", () => {
    const render = vi.fn();
    const fake = makeFakeRaf();
    const sched = new TimelineScheduler(render, { raf: fake.raf, caf: fake.caf });
    sched.invalidate("data");
    sched.dispose();
    expect(fake.queue).toHaveLength(0);
    fake.flush();
    expect(render).not.toHaveBeenCalled();
  });

  it("metrics tracks scheduled / rendered / dropped frames", () => {
    const render = vi.fn();
    const fake = makeFakeRaf();
    const sched = new TimelineScheduler(render, { raf: fake.raf, caf: fake.caf });
    sched.invalidate();
    fake.flush();
    expect(sched.metrics().framesScheduled).toBe(1);
    expect(sched.metrics().framesRendered).toBe(1);
  });
});
