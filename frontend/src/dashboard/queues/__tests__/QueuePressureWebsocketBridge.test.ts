import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  makeQueuePressureSubscribeFactory,
  queueMetricsPayloadFromEnvelope,
} from "@/dashboard/queues/hooks/useQueuePressureWebsocketBridge";
import { useQueuePressureStore } from "@/dashboard/queues/QueuePressureStore";
import {
  makePressureChange,
  makeRecord,
  makeHydration,
} from "@/dashboard/queues/__fixtures__/queuePressureFixtures";
import type { RuntimeEnvelope } from "@/types/runtime";

const envelope = (payload: unknown): RuntimeEnvelope => ({
  protocol_version: "1",
  type: "runtime_event",
  timestamp: 0,
  payload: payload as Record<string, unknown>,
});

beforeEach(() => {
  useQueuePressureStore.getState().reset();
});

describe("queueMetricsPayloadFromEnvelope", () => {
  it("returns null for non-queue event_type", () => {
    expect(
      queueMetricsPayloadFromEnvelope(envelope({ event_type: "asyncio.task.created" })),
    ).toBeNull();
  });

  it("returns the payload for matching event_type", () => {
    const payload = makePressureChange();
    const out = queueMetricsPayloadFromEnvelope(envelope(payload));
    expect(out).not.toBeNull();
    expect(out!.queue_id).toBe(payload.queue_id);
  });

  it("returns null for empty payloads", () => {
    expect(queueMetricsPayloadFromEnvelope(envelope({}))).toBeNull();
  });
});

describe("makeQueuePressureSubscribeFactory", () => {
  it("forwards matching envelopes to the apply callback", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const factory = makeQueuePressureSubscribeFactory(source);
    const apply = vi.fn();
    factory(apply);
    listeners[0](envelope(makePressureChange({ queue_id: "q-z" })));
    expect(apply).toHaveBeenCalledTimes(1);
    expect(apply.mock.calls[0][0].queue_id).toBe("q-z");
  });

  it("skips non-queue envelopes without invoking apply", () => {
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const apply = vi.fn();
    makeQueuePressureSubscribeFactory(source)(apply);
    listeners[0](envelope({ event_type: "asyncio.task.created" }));
    expect(apply).not.toHaveBeenCalled();
  });

  it("integrates end-to-end with the store via apply", () => {
    useQueuePressureStore
      .getState()
      .hydrateSnapshot(makeHydration({ queues: [makeRecord({ queue_id: "q-1" })] }));
    const listeners: Array<(envelope: RuntimeEnvelope) => void> = [];
    const source = {
      subscribe(_filter: "runtime_event", listener: (envelope: RuntimeEnvelope) => void) {
        listeners.push(listener);
        return { unsubscribe: () => {} };
      },
    };
    const factory = makeQueuePressureSubscribeFactory(source);
    factory((payload) => useQueuePressureStore.getState().applyEventPayload(payload));
    listeners[0](envelope(makePressureChange({ queue_id: "q-1", new_level: "critical" })));
    const state = useQueuePressureStore.getState();
    expect(state.recordsById["q-1"]?.pressure.level).toBe("critical");
    expect(state.markers).toHaveLength(1);
  });
});
