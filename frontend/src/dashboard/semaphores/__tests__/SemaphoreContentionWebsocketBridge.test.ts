import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  makeSemaphoreContentionSubscribeFactory,
  semaphorePayloadFromEnvelope,
} from "@/dashboard/semaphores/hooks/useSemaphoreContentionWebsocketBridge";
import { useSemaphoreContentionStore } from "@/dashboard/semaphores/SemaphoreContentionStore";
import {
  makeContention,
  makeCreated,
  makeHydration,
  makeIdentity,
} from "@/dashboard/semaphores/__fixtures__/semaphoreContentionFixtures";
import type { RuntimeEnvelope } from "@/types/runtime";

const envelope = (payload: unknown): RuntimeEnvelope => ({
  protocol_version: "1",
  type: "runtime_event",
  timestamp: 0,
  payload: payload as Record<string, unknown>,
});

beforeEach(() => {
  useSemaphoreContentionStore.getState().reset();
});

describe("semaphorePayloadFromEnvelope", () => {
  it("returns null for non-semaphore event_type", () => {
    expect(
      semaphorePayloadFromEnvelope(envelope({ event_type: "asyncio.task.created" })),
    ).toBeNull();
  });

  it("returns the payload for matching event_type", () => {
    const payload = makeContention();
    const out = semaphorePayloadFromEnvelope(envelope(payload));
    expect(out).not.toBeNull();
    expect(out!.semaphore_id).toBe(payload.semaphore_id);
  });

  it("returns null for empty payloads", () => {
    expect(semaphorePayloadFromEnvelope(envelope({}))).toBeNull();
  });
});

describe("makeSemaphoreContentionSubscribeFactory", () => {
  it("forwards matching envelopes to apply", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeSemaphoreContentionSubscribeFactory(source)(apply);
    listeners[0](envelope(makeCreated({ semaphore_id: "s-z" })));
    expect(apply).toHaveBeenCalledTimes(1);
    expect(apply.mock.calls[0][0].semaphore_id).toBe("s-z");
  });

  it("skips non-semaphore envelopes without invoking apply", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeSemaphoreContentionSubscribeFactory(source)(apply);
    listeners[0](envelope({ event_type: "asyncio.task.created" }));
    expect(apply).not.toHaveBeenCalled();
  });

  it("integrates end-to-end with the store via apply", () => {
    useSemaphoreContentionStore.getState().hydrateSnapshot(
      makeHydration({ semaphores: [makeIdentity({ semaphore_id: "s-1" })] }),
    );
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    makeSemaphoreContentionSubscribeFactory(source)((payload) =>
      useSemaphoreContentionStore.getState().applyEventPayload(payload),
    );
    listeners[0](envelope(makeContention({ semaphore_id: "s-1", waiter_count: 3 })));
    const state = useSemaphoreContentionStore.getState();
    expect(state.recordsById["s-1"]?.waiterCount).toBe(3);
    expect(state.markers).toHaveLength(1);
  });
});
