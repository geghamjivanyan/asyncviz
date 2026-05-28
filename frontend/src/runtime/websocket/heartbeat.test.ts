import { describe, expect, it, vi } from "vitest";
import { HeartbeatMonitor } from "@/runtime/websocket/heartbeat";

interface FakeTimer {
  callback: () => void;
  delay: number;
}

function makeFakeTimers() {
  const timers = new Map<number, FakeTimer>();
  let nextId = 0;
  return {
    timers,
    setTimer: (callback: () => void, delay: number) => {
      const id = ++nextId;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimer: (id: unknown) => {
      timers.delete(id as number);
    },
    fireOne: () => {
      const entries = [...timers.entries()];
      if (entries.length === 0) return;
      const [id, timer] = entries[0]!;
      timers.delete(id);
      timer.callback();
    },
  };
}

describe("HeartbeatMonitor", () => {
  it("does not fire onStale before the threshold", () => {
    const fake = makeFakeTimers();
    const onStale = vi.fn();
    const monitor = new HeartbeatMonitor({
      staleThresholdMs: 1000,
      setTimer: fake.setTimer,
      clearTimer: fake.clearTimer,
      now: () => 0,
    });
    monitor.start(onStale);
    // No timer firing means no stale callback.
    expect(onStale).not.toHaveBeenCalled();
  });

  it("fires onStale when no frame is recorded within the window", () => {
    const fake = makeFakeTimers();
    const onStale = vi.fn();
    const monitor = new HeartbeatMonitor({
      staleThresholdMs: 1000,
      setTimer: fake.setTimer,
      clearTimer: fake.clearTimer,
      now: () => 0,
    });
    monitor.start(onStale);
    fake.fireOne();
    expect(onStale).toHaveBeenCalledTimes(1);
    expect(monitor.staleTriggers).toBe(1);
  });

  it("recordFrame() restarts the timer and bumps heartbeat counter", () => {
    const fake = makeFakeTimers();
    const onStale = vi.fn();
    const monitor = new HeartbeatMonitor({
      staleThresholdMs: 1000,
      setTimer: fake.setTimer,
      clearTimer: fake.clearTimer,
      now: () => 0,
    });
    monitor.start(onStale);
    monitor.recordFrame(true);
    monitor.recordFrame(true);
    expect(monitor.heartbeatsSeen).toBe(2);
    // Each recordFrame cleared the prior timer and scheduled a new one.
    expect(fake.timers.size).toBe(1);
  });

  it("stop() cancels the pending timer", () => {
    const fake = makeFakeTimers();
    const onStale = vi.fn();
    const monitor = new HeartbeatMonitor({
      staleThresholdMs: 1000,
      setTimer: fake.setTimer,
      clearTimer: fake.clearTimer,
      now: () => 0,
    });
    monitor.start(onStale);
    monitor.stop();
    expect(fake.timers.size).toBe(0);
  });
});
