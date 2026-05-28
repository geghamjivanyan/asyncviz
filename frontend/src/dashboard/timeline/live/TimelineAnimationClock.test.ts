import { describe, expect, it, vi } from "vitest";
import { TimelineAnimationClock } from "@/dashboard/timeline/live/TimelineAnimationClock";

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
    pending: () => queue.length,
  };
}

describe("TimelineAnimationClock", () => {
  it("does not tick when there are zero active segments", () => {
    const fake = fakeRaf();
    const listener = vi.fn();
    const clock = new TimelineAnimationClock(listener, { raf: fake.raf, caf: fake.caf });
    fake.flush();
    expect(listener).not.toHaveBeenCalled();
    expect(clock.isRunning()).toBe(false);
  });

  it("starts ticking when the active count goes positive", () => {
    const fake = fakeRaf();
    const listener = vi.fn();
    const clock = new TimelineAnimationClock(listener, { raf: fake.raf, caf: fake.caf });
    clock.setActiveSegmentCount(2);
    expect(clock.isRunning()).toBe(true);
    fake.flush();
    expect(listener).toHaveBeenCalledTimes(1);
    fake.flush();
    expect(listener).toHaveBeenCalledTimes(2);
  });

  it("stops ticking when active count drops to zero", () => {
    const fake = fakeRaf();
    const listener = vi.fn();
    const clock = new TimelineAnimationClock(listener, { raf: fake.raf, caf: fake.caf });
    clock.setActiveSegmentCount(1);
    fake.flush();
    clock.setActiveSegmentCount(0);
    expect(clock.isRunning()).toBe(false);
    fake.flush();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("respects maxTicksPerSecond throttle", () => {
    const fake = fakeRaf();
    const listener = vi.fn();
    let now = 0;
    const clock = new TimelineAnimationClock(listener, {
      raf: fake.raf,
      caf: fake.caf,
      maxTicksPerSecond: 60,
      now: () => now,
    });
    clock.setActiveSegmentCount(1);
    fake.flush();
    now += 1;
    fake.flush();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(clock.metrics().ticksSuppressed).toBe(1);
  });

  it("pause stops the clock; resume restarts when still active", () => {
    const fake = fakeRaf();
    const listener = vi.fn();
    const clock = new TimelineAnimationClock(listener, { raf: fake.raf, caf: fake.caf });
    clock.setActiveSegmentCount(1);
    clock.pause();
    expect(clock.isRunning()).toBe(false);
    clock.resume();
    expect(clock.isRunning()).toBe(true);
  });

  it("dispose halts further ticks", () => {
    const fake = fakeRaf();
    const listener = vi.fn();
    const clock = new TimelineAnimationClock(listener, { raf: fake.raf, caf: fake.caf });
    clock.setActiveSegmentCount(1);
    clock.dispose();
    fake.flush();
    expect(listener).not.toHaveBeenCalled();
  });
});
