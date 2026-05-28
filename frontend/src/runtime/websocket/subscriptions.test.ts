import { describe, expect, it, vi } from "vitest";
import { SubscriptionRegistry } from "@/runtime/websocket/subscriptions";
import type { RuntimeEnvelope } from "@/types/runtime";

function envelope(type: RuntimeEnvelope["type"]): RuntimeEnvelope {
  return {
    protocol_version: "1.0",
    type,
    timestamp: 0,
    sequence: null,
    payload: {},
  };
}

describe("SubscriptionRegistry", () => {
  it("delivers to type-specific listeners only", () => {
    const registry = new SubscriptionRegistry();
    const metricsListener = vi.fn();
    const warningListener = vi.fn();
    registry.add("metrics_delta", metricsListener);
    registry.add("warning_delta", warningListener);

    registry.emit(envelope("metrics_delta"));
    expect(metricsListener).toHaveBeenCalledTimes(1);
    expect(warningListener).not.toHaveBeenCalled();
  });

  it("delivers to wildcard listeners on every envelope", () => {
    const registry = new SubscriptionRegistry();
    const wildcard = vi.fn();
    registry.add("*", wildcard);

    registry.emit(envelope("heartbeat"));
    registry.emit(envelope("runtime_event"));
    expect(wildcard).toHaveBeenCalledTimes(2);
  });

  it("unsubscribe() removes the listener", () => {
    const registry = new SubscriptionRegistry();
    const listener = vi.fn();
    const sub = registry.add("metrics_delta", listener);
    sub.unsubscribe();
    registry.emit(envelope("metrics_delta"));
    expect(listener).not.toHaveBeenCalled();
    expect(registry.size()).toBe(0);
  });

  it("counts errors raised by listeners but keeps fanning out", () => {
    const original = console.error;
    console.error = () => undefined;
    try {
      const registry = new SubscriptionRegistry();
      const failing = vi.fn(() => {
        throw new Error("boom");
      });
      const succeeding = vi.fn();
      registry.add("metrics_delta", failing);
      registry.add("metrics_delta", succeeding);
      registry.emit(envelope("metrics_delta"));
      expect(failing).toHaveBeenCalled();
      expect(succeeding).toHaveBeenCalled();
      expect(registry.errors()).toBe(1);
    } finally {
      console.error = original;
    }
  });

  it("clear() drops every subscription", () => {
    const registry = new SubscriptionRegistry();
    registry.add("metrics_delta", () => undefined);
    registry.add("warning_delta", () => undefined);
    registry.clear();
    expect(registry.size()).toBe(0);
  });

  it("sizeFor() returns count per filter", () => {
    const registry = new SubscriptionRegistry();
    registry.add("metrics_delta", () => undefined);
    registry.add("metrics_delta", () => undefined);
    registry.add("warning_delta", () => undefined);
    registry.add("*", () => undefined);
    expect(registry.sizeFor("metrics_delta")).toBe(2);
    expect(registry.sizeFor("warning_delta")).toBe(1);
    expect(registry.sizeFor("*")).toBe(1);
    expect(registry.size()).toBe(4);
  });
});
